#!/bin/bash
set -euo pipefail
rm -f /etc/apt/apt.conf.d/docker-clean /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list
cat > /etc/apt/sources.list.d/snapshot.sources <<'EOS'
Types: deb
URIs: https://snapshot.ubuntu.com/ubuntu/20261024T000000Z/
Suites: noble noble-updates noble-security
Components: main universe
Architectures: amd64
Signed-By: /in/ubuntu-archive-keyring.gpg
EOS
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d; chmod 755 /usr/sbin/policy-rc.d
echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99snapshot
echo 'APT::Keep-Downloaded-Packages "true";' >> /etc/apt/apt.conf.d/99snapshot
echo 'Acquire::https::CaInfo "/in/ca.crt";' >> /etc/apt/apt.conf.d/99snapshot
export DEBIAN_FRONTEND=noninteractive
dpkg-query -W -f='${binary:Package} ${Version}\n' | sort > /out/base-packages.txt
apt-get update
mapfile -t roots < /in/roots.txt
apt-get install --yes --no-install-recommends "${roots[@]}" 2>&1 | tail -40
dpkg-query -W -f='${binary:Package} ${Version}\n' | sort > /out/installed-packages.txt
wc -l /out/base-packages.txt /out/installed-packages.txt
