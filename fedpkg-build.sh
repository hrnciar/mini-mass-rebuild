set -o pipefail  # make tee preserve the exit code
fedpkg clone $1 -- --branch rawhide 2>&1 | tee ./${1}.log || exit $?

cd $1
  fedpkg build --target=f35-python --fail-fast --nowait --background 2>&1 | tee -a ../${1}.log
cd -

rm -rf $1
