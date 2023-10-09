##### build stage ##############################################################

ARG TARGET_ARCHITECTURE
ARG BASE=7.0.7ec2
ARG REGISTRY=ghcr.io/epics-containers

FROM  ${REGISTRY}/epics-base-${TARGET_ARCHITECTURE}-developer:${BASE} AS developer

COPY . /epics/ioc-PandABlocks
WORKDIR /epics/ioc-PandABlocks
RUN pip install --upgrade pip && \
    pip install .

##### runtime preparation stage ################################################

FROM developer AS runtime_prep

# get the products from the build stage and reduce to runtime assets only
RUN ibek ioc extract-runtime-assets /assets --no-defaults --extras /venv

##### runtime stage ############################################################

FROM ${REGISTRY}/epics-base-${TARGET_ARCHITECTURE}-runtime:${BASE} AS runtime

# get runtime assets from the preparation stage
COPY --from=runtime_prep /assets /

ENV TARGET_ARCHITECTURE ${TARGET_ARCHITECTURE}

ENTRYPOINT ["/bin/bash"]
