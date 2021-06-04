set -o pipefail  # make tee preserve the exit code
fedpkg clone $1 -- --branch rawhide 2>&1 | tee ./${1}.log || exit $?

cd $1
  if ! git show --name-only | grep -F "Python 3.10"; then
    rpmdev-bumpspec -c "Rebuilt for Python 3.10" --userstring="Python Maint <python-maint@redhat.com>" *.spec | tee -a ../${1}.log
    git commit *.spec -m "Rebuilt for Python 3.10" --author="Python Maint <python-maint@redhat.com>" | tee -a ../${1}.log
    git push
  fi
  fedpkg build --target=f35-python --skip-remote-rules-validation --fail-fast --nowait --background 2>&1 | tee -a ../${1}.log
cd -

rm -rf $1
