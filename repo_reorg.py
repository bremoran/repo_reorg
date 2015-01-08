#!/usr/bin/python
# PackageLicenseDeclared: Apache-2.0
# Copyright 2015 ARM Holdings PLC
import argparse as ap
import sys
import os.path
import subprocess
import shutil
import stat
#Inputs:
#Source remote
#Destination remote
#Repo name
#List of paths in form: source-path:destination-path

moduleJsonTemplate = '''
{{
    "name": "{0}",
    "version": "0.0.0",
    "description": "",
    "keywords": [
    ],
    "author": "name <email@arm.com>",
    "repository": {{
        "url": "git@github.com:ARMmbed/{0}.git",
        "type": "git"
    }},
    "homepage": "https://github.com/ARMmbed/{0}",
    "license": "Apache-2",
    "dependencies": {{
    }},
    "extraIncludes": ["{0}"],
    "targetDependencies": {{
    }}
}}
'''

def mkparser():
    parser = ap.ArgumentParser(description='Create a new git repo, filtering the contents out of an existing one')
    parser.add_argument('-o', '--origin', help='The source repository', type=str, required=True)
    parser.add_argument('-b', '--origin-branch', help='The branch of the origin to clone', type=str, dest='branch', default='master')
    parser.add_argument('-d', '--destination', help='The destination repository (optional)', type=str)
    parser.add_argument('-n', '--name', help='The name of the repo to create',type=str)
    parser.add_argument('-f', '--file', metavar='FILE',
        help='Load the paths to merge out of FILE.  The format of the path arguments must be followed, one path per line.',
        type=str)
    parser.add_argument('path', metavar='P', nargs='*',
        help='Paths to include in the new repo.  Paths must be of the form: <old repo path>:<new repo path>')
    return parser

def remove_readonly(func, path, excinfo):
    if os.path.isfile(path) or os.path.isdir(path):
        os.chmod(path, stat.S_IWRITE)
        func(path)

def parseargs(parser):
    opts = parser.parse_args()
    return opts

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

def mkpaths(parser, paths, file):
    pths = paths[:]
    if file:
        try:
            f = open(file)
            for line in f:
                line = line.strip()
                pths.append(line)
            f.close()
        except IOError as e:
            print "Error processing {2}; I/O error({0}): {1}".format(e.errno, e.strerror, file)

    if len(pths) < 1:
        print('Error: no mapping specified.')
        sys.exit(1)
    pathmap = {}
    for path in pths:
        l = path.split(':')
        if len(l) != 2:
            print('ERROR: Unrecognized path format: %s'%path)
            parser.print_help()
            sys.exit(1)
        sp = os.path.join(*pathsplit(l[0]))
        pathmap[sp] = l[1]
    # Check for duplicate targets
    l = pathmap.values()
    dupes = set([x for x in l if l.count(x) > 1])
    if len(dupes):
        print 'ERROR: Duplicate target path entries:'
        for p in dupes:
            print p
        sys.exit(1)

    return pathmap

def canCollapse(n,total):
    return n==total

def collapsePaths(opts, workroot, dpathmap):
    # Get the origin repo directory
    repodir = os.path.join(workroot,'origin')
    altered = True
    while altered:
        for path in dpathmap:
            realPath = os.path.join(repodir,path)
            # Get the path's parent directory
            parentPath = os.path.dirname(path)
            realParentPath = os.path.dirname(realPath)
            # Get a list of sibling directories
            root, sibs, sibfiles = next(os.walk(realParentPath))
            sibPaths = [os.path.relpath(os.path.join(root,x),repodir) for x in sibs]
            sibCount = 0
            # print 'Checking for keys in dpathmap:', sibPaths
            for sib in sibPaths:
                if sib in dpathmap:
                    sibCount+=1
            # print 'Trying to collapse {0} into {1} ({2}/{3})'.format(path,parentPath,sibCount,len(sibPaths))
            if canCollapse(sibCount,len(sibPaths)):
                #print 'collapsing...'
                #Promote all siblings' children to parent children
                if not parentPath in dpathmap:
                    dpathmap[parentPath] = {}
                for sib in sibPaths:
                    if not sib in dpathmap:
                        continue
                    nephews = dpathmap[sib]
                    for neph,target in nephews.iteritems():
                        sibrel = os.path.relpath(sib,parentPath)
                        dpathmap[parentPath][os.path.join(sibrel,neph)] = target
                    #remove sibling from dpathmap
                    del dpathmap[sib]
                break
            # else:
                # print 'Failed to collapse {0}'.format(path)

        else:
            altered = False
    return dpathmap

def mkDistinctPaths(pathmap):
    dpathmap = {}
    # Just get the directories in sorted order
    lp = sorted(list(set(map(os.path.dirname,pathmap.keys()))))# [os.path.join(*x[:-1]) for x in map(pathsplit,pathmap.keys())])))

    for p in lp:
        for k in dpathmap:
            rp = os.path.relpath(p,k)
            if rp[0:2] != '..':
                break
        else:
            dpathmap[p] = {}
    # Insert the paths into the distinct path map
    for p,target in pathmap.iteritems():
        for k in dpathmap:
            rp = os.path.relpath(p,k)
            if rp[0:2] != '..':
                dpathmap[k][rp] = target
                break
        else:
            print 'ERROR: %s not handled!'%p
    return dpathmap

def getOrigin(opts,workroot):
    repodir = os.path.join(workroot,'origin')
    if os.path.isdir(os.path.join(repodir,'.git')):
        os.chdir(repodir)
        rc = subprocess.call(['git','pull','origin',opts.branch],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
        if rc != 0:
            print '\nFailed to update repo: %s'%opts.origin
            sys.exit(1)
    else:
        print 'Importing origin...'
        rc = subprocess.call(['git','clone','--branch',opts.branch,'--single-branch', opts.origin, repodir],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
        if rc != 0:
            print '\nFailed to clone repo: %s'%opts.origin
            sys.exit(1)
    os.chdir(workroot)

def cloneFilter(opts, workroot, name, path):
    repodir = os.path.join(workroot,name)
    rc = subprocess.call(['git','clone', os.path.join(workroot,'origin'), repodir],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
    if rc != 0:
        print '\nFailed to clone repo %s into %s'%(os.path.join(workroot,'origin'), repodir)
        sys.exit(1)
    os.chdir(repodir)
    rc = subprocess.call(['git','filter-branch','-f','--prune-empty','--subdirectory-filter',path],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
    # if rc != 0:
    #     print '\nFailed to filter %s, subdirectory %s'%(repodir, path)
    #     sys.exit(1)

def testCommit(repodir,msg):
    cwd = os.getcwd()
    os.chdir(repodir)
    rc = subprocess.call('git diff-index --cached --quiet HEAD --ignore-submodules'.split())
    if rc:
        rc = subprocess.call(['git','commit','-m',msg])
        if rc != 0:
            print '\nFailed to commit %s'%(repodir)
            sys.exit(1)
    os.chdir(cwd)

def filterRepo(opts,workroot,dpathmap):
    print 'Importing and filtering repos'
    fragments = dpathmap.keys()
    fragmap = {}
    i=0
    for fragment in fragments:
        print 'Processing fragment %d/%d (%s)'%(i+1,len(fragments),fragment)
        repoDir = os.path.join(workroot,'origin%d'%i)
        if os.path.isdir(repoDir):
            shutil.rmtree(repoDir)
        cloneFilter(opts,workroot,'origin%d'%i,fragment)
        fragmap[fragment]='origin%d'%i
        repodir = os.path.join(workroot,'origin%d'%i)
        msg = 'Filter %s for creation of new repo, %s.\nFragment %d/%d'%(os.path.join(workroot,'origin'),'origin%d'%i,i+1,len(fragments))
        testCommit(repodir,msg)
        os.chdir(repodir)
        # Get the current branch name
        branch = subprocess.check_output(['git','rev-parse','--abbrev-ref','HEAD'])
        branch = str(branch).strip()
        if branch != 'master':
            rc = subprocess.call(['git','checkout','-b','master'])
            if rc != 0:
                print '\nFailed to checkout master branch of %s'%(repodir)
                sys.exit(1)
        os.chdir(workroot)

        i+=1
    return fragmap

def rearrangeRepos(opts,workroot,dpathmap,fragmap):
    for d,files in dpathmap.iteritems():
        repodir = os.path.join(workroot,fragmap[d])
        os.chdir(repodir)
        for f,target in files.iteritems():
            subprocess.call(['mkdir','-p',os.path.dirname(target)])
            rc = subprocess.call(('git mv -f %s %s'%(f,target)).split(),stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
            if rc != 0:
                print '\nFailed to move %s to %s'%(f,target)
                sys.exit(1)
        filekeys = files.values()
        for root, subFolder, files in os.walk(repodir):
            for item in files:
                fn = os.path.join(root,item)
                fn = os.path.relpath(fn,repodir)
                if not fn in filekeys and os.path.isfile(fn) and not '.git' in fn:
                    subprocess.call(['git','rm',fn])
        rc = subprocess.call(['git','commit','-m','Rearrange %s in preparation for merge'%d],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
        if rc != 0:
            print '\nFailed to commit %s'%(repodir)
            sys.exit(1)
    os.chdir(workroot)

def createRepo(opts,workroot):
    newRepoDir = os.path.join(workroot,'newRepo')
    if os.path.isdir(newRepoDir):
        shutil.rmtree(newRepoDir,onerror=remove_readonly)
    rc = subprocess.call(['mkdir','-p',newRepoDir])
    if rc != 0:
        print '\nFailed to create directory: %s'%(newRepoDir)
        sys.exit(1)
    os.chdir(newRepoDir)
    rc = subprocess.call(['git','init'])
    if rc != 0:
        print '\nFailed to initialize git repo in: %s'%(newRepoDir)
        sys.exit(1)

    #testCommit(newRepoDir,'Initial commit of %s'%opts.name)

    os.chdir(workroot)
    return newRepoDir

def addRemotes(opts,workroot,fragmap,newRepoDir):
    os.chdir(newRepoDir)
    for frag,d in fragmap.iteritems():
        dpath = os.path.join(workroot,d)
        relpath = os.path.relpath(dpath,newRepoDir)
        rc = subprocess.call(['git','remote','add',d,relpath],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
        if rc != 0:
            print '\nFailed to add remote %s'%(d)
            sys.exit(1)
        rc = subprocess.call(['git','fetch',d],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
        if rc != 0:
            print '\nFailed to fetch remote %s'%(d)
            sys.exit(1)

    os.chdir(workroot)

def mergeRepos(opts,workroot,fragmap,newRepoDir):
    os.chdir(newRepoDir)
    for frag,d in fragmap.iteritems():
        rc = subprocess.call(['git','merge','%s/master'%d,'-m','Merge %s into %s'%(frag,opts.name)])
        if rc != 0:
            print '\nFailed to fetch merge remote %s'%(d)
            sys.exit(1)
    os.chdir(workroot)

def addModuleJson(opts,workroot,newRepoDir):
    os.chdir(newRepoDir)
    moduleJson = os.path.join(newRepoDir,'module.json')
    if os.path.isfile(moduleJson):
        return
    f = open(moduleJson,'w')
    f.write(moduleJsonTemplate.format(opts.name))
    f.close()
    rc = subprocess.call(['git','add',moduleJson],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
    if rc != 0:
        print '\nFailed to add %s to %s'%(moduleJson,newRepoDir)
        sys.exit(1)
    os.chdir(workroot)

def finalCommit(opts,workroot,newRepoDir):
    msg = 'Completed refactoring of %s into %s and added module.json'%(opts.origin,opts.name)
    testCommit(newRepoDir,msg)

def cleanup(opts,workroot,newRepoDir,fragmap):
    shutil.rmtree(os.path.join(workroot,'origin'),onerror=remove_readonly)
    os.chdir(newRepoDir)
    for frag,d in fragmap.iteritems():
        rc = subprocess.call(['git','remote','rm',d],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
        if rc != 0:
            print '\nFailed to remove %s from %s'%(d,newRepoDir)
            sys.exit(1)
        shutil.rmtree(os.path.join(workroot,d),onerror=remove_readonly)
    for f in os.listdir(newRepoDir):
        shutil.move(f,workroot)
    os.chdir(workroot)
    os.rmdir(newRepoDir)

#1: clone the source repo into ./origin
#2: clone the ./origin repo into numbered subdirectories(origin1, origin2,...)
#3: subdirectory-filter each origin#
#4: git init ./dest
#5: add a remote for each origin#
#6: fetch each origin
#7: merge each origin into ./dest

def main():
    parser = mkparser()
    opts = parseargs(parser)
    pathmap = mkpaths(parser, opts.path, opts.file)
    dpathmap = mkDistinctPaths(pathmap)
    # for k,files in dpathmap.iteritems():
    #     print '%s'%k
    #     for f,target in files.iteritems():
    #         print '\t%s -> %s'%(f,target)


    # Create the target directory...
    workroot = os.path.abspath(opts.name)
    rc = subprocess.call(['mkdir', '-p', workroot])
    if rc != 0:
        print '\nFailed to create directory: %s'%(workroot)
        sys.exit(1)

    os.chdir(workroot)
    # Get the origin repo
    getOrigin(opts, workroot)
    # Collapse the distinct paths where possible
    dpathmap = collapsePaths(opts, workroot, dpathmap)
    # Clone each fragment repo and filter for the fragment
    fragmap = filterRepo(opts, workroot, dpathmap)

    rearrangeRepos(opts,workroot,dpathmap,fragmap)
    newRepoDir = createRepo(opts,workroot)
    addRemotes(opts,workroot,fragmap,newRepoDir)
    mergeRepos(opts,workroot,fragmap,newRepoDir)
    addModuleJson(opts,workroot,newRepoDir)
    finalCommit(opts,workroot,newRepoDir)
    cleanup(opts,workroot,newRepoDir,fragmap)
    if opts.destination:
        rc = subprocess.call(['git','remote','add','origin',opts.destination],stderr=sys.stderr,stdout=sys.stdout,stdin=sys.stdin)
        if rc != 0:
            print '\nFailed to add remote (%s) to %s'%(opts.destination,opts.name)
            sys.exit(1)


if __name__=='__main__':
    main()
