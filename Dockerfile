##### build stage ##############################################################

ARG TARGET_ARCHITECTURE
ARG BASE=7.0.7ec2
ARG REGISTRY=ghcr.io/epics-containers

FROM  ${REGISTRY}/epics-base-linux-developer:${BASE} AS developer
ARG PIP_OPTIONS=.

# Copy any required context for the pip install over
COPY . /context
WORKDIR /context

# TEMPORARY use of alpha dependencies
# install python package into /venv
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev
RUN pip install ${PIP_OPTIONS}
RUN pip install epicscorelibs==7.0.7.99.1.0a1 pvxslibs==1.2.4a3
RUN pip install git+https://github.com/dls-controls/pythonSoftIOC.git --no-dependencies
# END TEMPORARY
# RUN pip install ${PIP_OPTIONS}

##### runtime preparation stage ################################################

FROM developer AS runtime_prep

# get the products from the build stage and reduce to runtime assets only
RUN ibek ioc extract-runtime-assets /assets --no-defaults --extras /venv

##### runtime stage ############################################################

FROM ${REGISTRY}/epics-base-linux-runtime:${BASE} AS runtime

# get runtime assets from the preparation stage
COPY --from=runtime_prep /assets /

ENV TARGET_ARCHITECTURE linux

ENTRYPOINT ["/bin/bash"]
