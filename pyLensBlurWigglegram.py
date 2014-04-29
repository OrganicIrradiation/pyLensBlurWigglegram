import argparse
import base64
import math
import numpy as np
import os
import re
import StringIO
import sys
from images2gif import writeGif
from PIL import Image
from scipy import interpolate

parser = argparse.ArgumentParser(description='Script that extracts the depth image for a Google Lens Blur image and uses it to create a Wigglegram')
parser.add_argument('i', metavar='INPUTFILENAME', type=str,
                   help='the JPG file to be processed')
parser.add_argument('-o', metavar='OUTPUTFILENAME', type=str,
                   help='optional filename of the output GIF (defaults to the input filename')
parser.add_argument('-d', metavar='DEPTHMIDPOINT', type=float, default=0.5,
                   help='depth mid-point, proportion with 0.0 being closest to viewer and 1.0 being furthest (default: %(default)s)')
parser.add_argument('-fd', metavar='FRAMEDELAY', type=float, default=0.05,
                   help='delay between GIF frames, in miliseconds (default: %(default)s)')
parser.add_argument('-fn', metavar='FRAMENUM', type=int, default=20,
                   help='total number of GIF frames (default: %(default)s)')
parser.add_argument('-m', metavar='MAGNITUDE', type=float, default=20.0,
                   help='displacement amplitude in pixels (default: %(default)s)')
parser.add_argument('-ri', metavar='RESIZEINITIAL', type=float, default=1.0,
                   help='proportion to resize the initial image (default: %(default)s)')
parser.add_argument('-rf', metavar='RESIZEFINAL', type=float, default=0.5,
                   help='proportion to resize the final image, relative to the intially resized image (default: %(default)s)')

args = parser.parse_args()

if not os.path.isfile(args.i):
    raise Exception('Input Filename does not exist')
if not args.o:
    fileName, fileExtension = os.path.splitext(args.i)
else:
    fileName, fileExtension = os.path.splitext(args.o)
args.o = fileName+'.gif'

def displaceImage(imgI,imgD,amount):
    I = np.array(imgI)
    D = np.array(imgD)/255.0
    D = (D - D.min())/(D.max() - D.min()) - args.d

    height, width, colors = I.shape
    # Initializing the output image array with zeros
    O = np.zeros([height,width,colors],dtype='uint8')

    # Calculate the new displaced locations as a function of the depth map
    [X,Y] = np.meshgrid(range(0,width),range(0,height))
    newX = X+D*amount[0]
    newX = np.maximum(np.minimum(newX,width-1),0)
    newY = Y+D*amount[1]
    newY = np.maximum(np.minimum(newY,height-1),0)
    points = np.concatenate((newX.reshape(-1,1),newY.reshape(-1,1)),axis=1)

    # Need to go through each color and interpolate along that dimension
    for color in range(0,colors):
        print 'Processing Color',color
        values = I[:,:,color].reshape(-1,1)
        grid = interpolate.griddata(points, values, (X,Y), method='linear')
        O[:,:,color] = grid.T[0,:,:].transpose()
    return Image.fromarray(O)

def resizeImage(inI,ratio):
    I = inI.copy()
    width, height = I.size
    I = I.convert("RGB")
    I=I.resize((int(width*ratio),int(height*ratio)), Image.ANTIALIAS)
    return I

def cleanString(strIn):
    # Gets rid of the XMP format trash that has nothing to do with out PNGs
    strIn = strIn.replace('\n','\xFF')
    match = re.findall(r'.{4}http:[^\x00]*.[^\x00]*.{8}', strIn)
    for stupidString in match:
        strIn = strIn.replace(stupidString,'')
    return strIn

## Start of script
f = open(args.i, 'r')
data = f.read()
f.close()

# Extract the original (unblurred) image
image_start = data.find('GImage:Data="')+len('GImage:Data="')
image_end = data.find('"',image_start+1)
image_str = cleanString(data[image_start:image_end])
image = StringIO.StringIO()
image.write(base64.b64decode(image_str))
image.seek(0)

# Extract the depth image
depth_start = data.find('GDepth:Data="')+len('GDepth:Data="')
depth_end = data.find('"/>',depth_start+1)
depth_str = data[depth_start:depth_end]
depth_str = cleanString(depth_str)
depth = StringIO.StringIO()
depth.write(base64.b64decode(depth_str))
depth.seek(0)

# Load the images
imgI = resizeImage(Image.open(image),args.ri)
imgD = resizeImage(Image.open(depth),args.ri).convert('L')
width, height = imgD.size

# Process the frames by displacing the image successively around a circle
frames = []
for theta in np.arange(0, 2*np.pi, 2*np.pi/args.fn):
    displaceV = (np.cos(theta) * args.m,np.sin(theta) * args.m)
    print 'Processing #',theta*args.fn/(2*np.pi),'of',args.fn,'-',displaceV
    processedImg = displaceImage(imgI,imgD,displaceV)
    processedImg = processedImg.crop((int(args.m),int(args.m),int(width-args.m*2),int(height-args.m*2)))
    processedImg = resizeImage(processedImg,args.rf)
    frames.append(processedImg)
    
## Save an initial wigglegram GIF
writeGif(args.o, frames, duration=args.fd)
## Re-save, but with an optimized palette (this takes quite a bit longer)
writeGif(args.o, frames, duration=args.fd, dither=True, nq=5, subRectangles=False)
