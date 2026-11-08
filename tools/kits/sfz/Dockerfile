# Builds sfizz_render (the command-line SFZ sampler, sfizz 1.2.3) from source on Debian trixie.
# sfizz is not a Debian package and its 1.2.3 release has no Linux binary, so this is the only way to get it.
# Nothing is installed on the host. Run it through ~/.claude/scripts/docker-heavy.sh (see sfz_render.py).
#
#   docker build -t beatboard-sfizz tools/kits/sfz
FROM debian:trixie-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git cmake g++ make pkg-config libsndfile1-dev \
 && rm -rf /var/lib/apt/lists/*
ARG SFIZZ_TAG=1.2.3
RUN git clone --depth 1 --branch ${SFIZZ_TAG} --recurse-submodules --shallow-submodules https://github.com/sfztools/sfizz.git /src
WORKDIR /src/build
RUN cmake .. -DCMAKE_BUILD_TYPE=Release \
      -DSFIZZ_JACK=OFF -DSFIZZ_RENDER=ON -DSFIZZ_LV2=OFF -DSFIZZ_VST=OFF -DSFIZZ_PUREDATA=OFF \
      -DSFIZZ_TESTS=OFF -DSFIZZ_DEMOS=OFF -DSFIZZ_DEVTOOLS=OFF -DSFIZZ_BENCHMARKS=OFF \
 && cmake --build . --target sfizz_render -j4 \
 && strip clients/sfizz_render \
 && cp clients/sfizz_render /sfizz_render

FROM debian:trixie-slim
# sox and ffmpeg do the mix (reverb, EQ, compression, loudness) in the same container.
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 sox ffmpeg libstdc++6 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /sfizz_render /usr/local/bin/sfizz_render
ENTRYPOINT []
