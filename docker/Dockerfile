# One image for CI (and later the Namespace Devbox): kicad-cli 9 + ngspice 46 + Python 3.11 sim stack.
# Build context = repository root:  docker build -f docker/Dockerfile -t plant-sensor-ci .
#
# Base: kicad/kicad:9.0.9 is Debian bookworm (verified from the image config). bookworm's own ngspice is 39,
# which is too old, so ngspice comes from bookworm-backports (46+ds-1~bpo12+1) instead of a source build.

ARG KICAD_TAG=9.0.9
FROM kicad/kicad:${KICAD_TAG}
#Start from original kicad image
USER root
RUN echo "deb http://deb.debian.org/debian bookworm-backports main" > /etc/apt/sources.list.d/backports.list \
#Get all our python / ngspice packages
    && apt-get update \
    && apt-get install -y --no-install-recommends -t bookworm-backports ngspice \
    && apt-get install -y --no-install-recommends \
        python3 python3-numpy python3-scipy python3-pandas python3-yaml python3-matplotlib \
        git make ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Vendor SPICE models below. They aren't allowed to be redistributed, thus aren't commited
ENV VENDOR_MODELS=/opt/vendor-models
RUN mkdir -p ${VENDOR_MODELS}

# kicad-cli writes config under $HOME; CI runs the container as the runner's uid, so use a world-writable HOME.
ENV HOME=/tmp/home
RUN mkdir -p /tmp/home && chmod 1777 /tmp/home \
    && ngspice --version | head -n 2 && kicad-cli version && python3 --version

WORKDIR /work
CMD ["bash"]
#This creates one box with every tool so that we can get rid of the recuring apt-install's on every run
