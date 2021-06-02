import pathlib
import rpm

SIGNS = {
    1: '>',
    0: '==',
    -1: '<',
}


def split(nevra):
    nev, _, ra = nevra.rpartition('-')
    n, _, ev = nev.rpartition('-')
    e, _, v = ev.rpartition(':')
    e = e or '0'
    r, _, a = ra.rpartition('.')
    if r.endswith('.src'):
        r = r[:-4]
    return n, (e, v, r)


def main():
    all_packages = set(pathlib.Path('python39.pkgs').read_text().splitlines())

    kojirepo = set(pathlib.Path('koji.repoquery').read_text().splitlines())
    py310repo = set(pathlib.Path('koji-python3.10.repoquery').read_text().splitlines())

    kojidict = dict(split(pkg) for pkg in kojirepo)
    py310dict = dict(split(pkg) for pkg in py310repo)

    todo = set()

    for pkg in sorted(all_packages):
        if pkg not in py310dict:
            continue
        sign = SIGNS[rpm.labelCompare(kojidict[pkg], py310dict[pkg])]
        print(f'{pkg: <30} {"-".join(kojidict[pkg])} {sign} {"-".join(py310dict[pkg])}')

        if sign == '>':
            todo.add(pkg)

    print()

    for pkg in sorted(todo):
        print(pkg)


if __name__ == '__main__':
    main()
