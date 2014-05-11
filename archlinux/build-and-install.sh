#! /bin/zsh

set -x

unset options

[ -r "$HOME/.makepkg.conf" ] && . "$HOME/.makepkg.conf"

cd "$0"(:h) &&
. ./PKGBUILD &&
pkgver="$(PYTHONPATH=.. python2 -c 'from mcomix.constants import VERSION; print VERSION')" &&
verrev="$(git blame -L '/^VERSION =/,+1' -l ../mcomix/constants.py | cut -c -40)" &&
pkgver="${pkgver/-SVN}.$(git rev-list --count "$verrev..").$(git log -1 --pretty='format:%h')" &&
src="src/$pkgname-$pkgver" &&
rm -rf src pkg &&
mkdir -p "$src" &&
cp -l "$pkgname.install" src/ &&
sed "s/^pkgver=.*\$/pkgver=$pkgver/" ./PKGBUILD >src/PKGBUILD &&
(cd "$OLDPWD" && git ls-files -z | xargs -0 cp -a --no-dereference --parents --target-directory="$OLDPWD/$src") &&
export PACKAGER="${PACKAGER:-`git config user.name` <`git config user.email`>}" &&
makepkg --noextract --force -p src/PKGBUILD &&
rm -rf src pkg &&
sudo pacman -U --noconfirm "$pkgname-$pkgver-$pkgrel-any${PKGEXT:-.pkg.tar.xz}"

