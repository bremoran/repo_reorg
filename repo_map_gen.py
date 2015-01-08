#!/usr/bin/python
# PackageLicenseDeclared: Apache-2.0
# Copyright 2015 ARM Holdings PLC
#
# Purpose:
# Generate a mapping file that translates between locations of files in two directories

import sys
import os
import argparse as ap

def mkparser():
    parser = ap.ArgumentParser(description='Generate a mapping file to translate between two directories')
    parser.add_argument('-o', '--origin', help='The source directory', type=str, required=True)
    parser.add_argument('-d', '--destination', help='The destination directory', type=str, required=True)
    parser.add_argument('-e', '--exclude-origin', help='Exclude DIR from origin path search', action='append')
    parser.add_argument('-E', '--exclude-destination', help='Exclude DIR from destination path search', action='append')
    parser.add_argument('-f', '--output-file', help='Output File', type=ap.FileType('w'), default=sys.stdout )
    return parser

def parseargs(parser):
    return parser.parse_args()

def pathsplit(p):
    parts = []
    while True:
        p, f = os.path.split(p)
        if len(f) == 0:
            if p: parts.append(p)
            break
        parts.append(f)
    parts.reverse()
    return parts

def prefixmatch(prefixlist, ilist):
    for prefix in prefixlist:
        for i,e in enumerate(prefix):
            if ilist[i] != e:
                break
        else:
            return True
    return False


def findFiles(directory,exclusions):
    directory = os.path.abspath(directory)
    fileList = []
    le = map(pathsplit, exclusions)
    for root, dirs, files in os.walk(directory):
        # make the files relative to directory
        rfiles = [os.path.relpath(f,directory) for f in [os.path.join(root,f) for f in files]]
        lfiles = map(pathsplit, rfiles)
        for lf in lfiles:
            if not prefixmatch(le,lf):
                fileList.append(os.path.join(*lf))
    return fileList

def fileMap(paths):
    fmap = {}
    uniqueFileNames = set(map(os.path.basename,paths))
    for fn in uniqueFileNames: fmap[fn]=[]
    for path in paths:
        dn,fn = os.path.split(path)
        fmap[fn].append(path)

    return fmap

def filterMap(dfOrigins):
    for destFile,originList in dfOrigins.iteritems():
        if len(originList) <= 1:
            continue
        destPathList = pathsplit(destFile)
        destFileName = destPathList[-1]
        origins = [(x,pathsplit(x)) for x in originList]
        matches = []
        while len(destPathList) != 0 and len(origins) > 1:
            matches = origins[:]
            nextOrigins = [(o[0],o[-1][:-1]) for o in origins if o[1] and o[1][-1] == destPathList[-1]]
            destPathList = destPathList[:-1]
            origins = nextOrigins
        if not origins:
            origins = matches
        dfOrigins[destFile] = [o[0] for o in origins]
    return dfOrigins

def main():
    # Generate the parser
    parser = mkparser()
    # Parse the input arguments
    opts = parseargs(parser)
    # Generate a list of files in the origin directory
    originPaths = findFiles(opts.origin,opts.exclude_origin)
    # Generate a list of files in the destination directory
    destPaths = findFiles(opts.destination,opts.exclude_destination)
    # Generate lists of paths for each filename in the origin
    originMap = fileMap(originPaths)
    # Generate a list of possible origins for each destination file
    dfOrigins = {}
    for p in destPaths:
        fn = os.path.basename(p)
        dfOrigins[p] = originMap.get(fn,[])

    # Filter the list of possible origins by path prefix
    dfOrigins = filterMap(dfOrigins)

    duplicates = False
    # For each file match pair
    for dpath, originList in dfOrigins.iteritems():
        # Print old:new
        if len(originList) > 1:
            duplicates = True
            for origin in originList:
                opts.output_file.write('#{1}:{0}\n'.format(dpath,origin))
                #print('#{0}:{1}'.format(dpath,origin))
        elif len(originList) == 0 or (len(originList) == 1 and originList[0] == ''):
            print('Warning: Could not find a match for {0}'.format(dpath))
        else:
            opts.output_file.write('{1}:{0}\n'.format(dpath,originList[0]))
            #print('{0}:{1}'.format(dpath,originList[0]))
    if duplicates:
        print('Warning, duplicates found, check %s for more detail'%opts.output_file.name)


if __name__ == '__main__':
    main()
