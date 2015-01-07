# repo_reorg
Python git repository reorganizer. repo_reorg.py can be used to selectively move files from an existing repo to new locations in a new repo, while preserving history.
```
usage: repo_reorg.py [-h] -o ORIGIN [-b BRANCH] [-d DESTINATION] [-n NAME]
                     [-f FILE]
                     [P [P ...]]

Create a new git repo, filtering the contents out of an existing one

positional arguments:
  P                     Paths to include in the new repo. Paths must be of the
                        form: <old repo path>:<new repo path>

optional arguments:
  -h, --help            show this help message and exit
  -o ORIGIN, --origin ORIGIN
                        The source repository
  -b BRANCH, --origin-branch BRANCH
                        The branch of the origin to clone
  -d DESTINATION, --destination DESTINATION
                        The destination repository (optional)
  -n NAME, --name NAME  The name of the repo to create
  -f FILE, --file FILE  Load the paths to merge out of FILE. The format of the
                        path arguments must be followed, one path per line.
```
