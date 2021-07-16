import dnf
import re
import subprocess
import sys
from collections import defaultdict

RAWHIDEVER = 35
DNF_CACHEDIR = '_dnf_cache_dir'
ARCH = 'x86_64'

sacks = {}

def rawhide_sack():
    try:
        return sacks[None]
    except KeyError:
        pass
    base = dnf.Base()
    conf = base.conf
    conf.cachedir = DNF_CACHEDIR
    conf.substitutions['releasever'] = str(RAWHIDEVER)
    conf.substitutions['basearch'] = ARCH
    base.repos.add_new_repo('rawhide', conf,
        metalink='https://mirrors.fedoraproject.org/metalink?repo=rawhide&arch=$basearch',
        skip_if_unavailable=False)
    base.fill_sack(load_system_repo=False, load_available_repos=True)
    sacks[None] = base.sack
    return base.sack


def fedora_sack(version):
    try:
        return sacks[version]
    except KeyError:
        pass
    base = dnf.Base()
    conf = base.conf
    conf.cachedir = DNF_CACHEDIR
    conf.substitutions['releasever'] = str(version)
    conf.substitutions['basearch'] = ARCH
    base.repos.add_new_repo(f'fedora{version}', conf,
        metalink='https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=$basearch',
        skip_if_unavailable=False,
        enabled=True)
    base.repos.add_new_repo(f'updates{version}',
        conf,
        metalink='https://mirrors.fedoraproject.org/metalink?repo=updates-released-f$releasever&arch=$basearch',
        skip_if_unavailable=False,
        enabled=True)
    base.repos.add_new_repo(f'updates-testing{version}', conf,
        metalink='https://mirrors.fedoraproject.org/metalink?repo=updates-testing-f$releasever&arch=$basearch',
        skip_if_unavailable=False,
        enabled=True)
    base.fill_sack(load_system_repo=False, load_available_repos=True)
    sacks[version] = base.sack
    return base.sack


def repoquery(*args, **kwargs):
    version = kwargs.pop('version', None)
    if version is None:
        sack = rawhide_sack()
    else:
        sack = fedora_sack(version)
    if 'whatrequires' in kwargs:
        package_name = kwargs['whatrequires']
        package = None
        for pkg in sack.query().available().filter(name=package_name,
                                                   latest=1).run():
            if pkg.arch != 'i686':
                return sack.query().available().filter(requires=[pkg])
        return []
    if 'whatrequires_exact' in kwargs:
        return sack.query().available().filter(requires=kwargs['whatrequires_exact'])
    if 'whatobsoletes' in kwargs:
        return sack.query().filter(obsoletes=kwargs['whatobsoletes'])
    if 'requires' in kwargs:
        pkgs = sack.query().filter(obsoletes=kwargs['requires'], latest=1).run()
        return pkgs[0].requires
    if 'all' in kwargs and kwargs['all']:
        return sack.query()
    raise RuntimeError('unknown query')


def old_pkgs():
    r = set()
    for version in (33,34):
        for dependency in ('python(abi) = 3.9',
                           'libpython3.9.so.1.0()(64bit)',
                           'libpython3.9d.so.1.0()(64bit)'):
            pkgs = repoquery(version=version,
                    whatrequires_exact=dependency)
            for pkg in pkgs:
                r.add(f'{pkg.name} {pkg.epoch}:{pkg.version}-{pkg.release}')
    return r


class SortableEVR:
    def __init__(self, evr):
        self.evr = evr

    def __repr__(self):
        return f"evr'{self.evr}'"

    def __eq__(self, other):
        return self.evr == other.evr

    def __lt__(self, other):
        return subprocess.call(('rpmdev-vercmp', self.evr, other.evr),
                               stdout=subprocess.DEVNULL) == 12


def removed_pkgs():
    name_versions = defaultdict(set)
    old_name_evrs = old_pkgs()
    new = set()
    for pkg in repoquery(all=True, version=None):
        new.add(f'{pkg.name}')
    seen = set()
    while old_name_evrs:
        name_evr = old_name_evrs.pop()
        name, _, evr = name_evr.partition(' ')
        if name not in new:
            name_versions[name].add(evr)
            for dependent in what_required(name):
                if dependent.split(' ')[0] not in seen:
                    old_name_evrs.add(dependent)
        seen.add(name)
    return {name: max(versions, key=SortableEVR)
            for name, versions in name_versions.items()}

def what_required(dependency):
    r = []
    for version in (33,34):
        pkgs = repoquery(version=version, whatrequires=dependency)
        for pkg in pkgs:
            r.append(f'{pkg.name} {pkg.epoch}:{pkg.version}-{pkg.release}')
    return r


def drop_dist(evr):
    ev, _, release = evr.rpartition('-')
    parts = (part for part in release.split('.') if not part.startswith('fc'))
    release = '.'.join(parts)
    return f'{ev}-{release}'


def drop_0epoch(evr):
    epoch, _, vr = evr.partition(':')
    return vr if epoch == '0' else evr


def bump_release(evr):
    ev, _, release = evr.rpartition('-')
    parts = release.split('.')
    release = []
    for part in parts:
        if part == '0':
            release.append(part)
        else:
            try:
                release.append(str(int(part) + 1))
            except ValueError:
                release.append(part)
                release.append("MANUAL")
            release = '.'.join(release)
            return f'{ev}-{release}'
    else:
        raise RuntimeError(f'Cannot bump {evr}')


def format_obsolete(pkg, evr):
    evr = bump_release(evr)
    return f'%obsolete {pkg} {evr}'


rp = removed_pkgs()
for pkg in sorted(rp):
    version = drop_0epoch(drop_dist(rp[pkg]))
    whatobsoletes = []
    obsoleters = repoquery(version=None, whatobsoletes=f'{pkg} = {version}')
    for obsoleter in obsoleters:
        whatobsoletes.append(f'{obsoleter.name}')
    if not whatobsoletes or whatobsoletes == ['fedora-obsolete-packages']:
        print(format_obsolete(pkg, version))
    else:
        obs = ', '.join(whatobsoletes)
        print(f'# {pkg} {version} obsoleted by {obs}', file=sys.stderr)
