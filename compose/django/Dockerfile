#syntax=docker/dockerfile:1
ARG STAGE=production

# ---------------------------------------------
# BEGIN build image stage
# ---------------------------------------------
FROM python:3.8-alpine as build
ARG STAGE=production

# only update build build when requirements have changed
COPY ./requirements /requirements
# install build dependencies
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
    apk update \
    && apk add --no-cache build-base \
    # psycopg2 dependencies
    && apk add --no-cache --virtual build-deps gcc python3-dev musl-dev \
    && apk add --no-cache postgresql-dev \
    # Pillow dependencies
    && apk add --no-cache jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev \
    # CFFI dependencies
    && apk add --no-cache libffi-dev py-cffi \
    # XLSX dependencies
    && apk add --no-cache libxml2-dev libxslt-dev \
    # Rust and Cargo required by the ``cryptography`` Python package - only required during build
    && apk add --no-cache rust \
    && apk add --no-cache cargo \
    # && pip install -r /requirements/${STAGE}.txt \
    # build wheels
    && pip install wheel && pip wheel --wheel-dir=/tmp/wheels -r /requirements/${STAGE}.txt \
    # remove the virtual package group 'build-deps'
    && apk del build-deps
# ---------------------------------------------
# END build image stage
# ---------------------------------------------

# ---------------------------------------------
# BEGIN django image stage
# ---------------------------------------------
FROM python:3.8-alpine as django
ARG STAGE=production

# stream python output for django logs
ENV PYTHONUNBUFFERED 1

ENV PYTHONPATH="$PYTHONPATH:/app/config"

ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN if [ -n "$(getent group ${USER_GID})" ]; \
      then \
        apk --no-cache add shadow; \
        groupmod -n "django" "${USER_GID}"; \
      else \
        addgroup --gid "${USER_GID}" "django"; \
    fi && \
    if [ -n "$(getent passwd ${USER_UID})" ]; \
      then \
        apk --no-cache add shadow; \
        usermod -l "django" -g "${USER_GID}" -d "/app"; \
      else \
        adduser \
          --home "/app" \
          --gecos "MAIL_DIR=/dev/null" \
          --shell /bin/ash \
          --ingroup "django" \
          --system \
          --disabled-password \
          --no-create-home \
          --uid "${USER_UID}" \
          "django"; \
    fi

# install runtime dependencies.  `add --no-cache` performs an apk update, adds packages and excludes caching
# in order to not require deletion of apk cache.
RUN apk add --no-cache postgresql-dev \
    # Pillow dependencies
    jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev \
    # CFFI dependencies
    libffi-dev py-cffi \
    # XLSX dependencies
    libxml2-dev libxslt-dev

# ensure that we are using the same requirements from the build stage
COPY --from=build /requirements /tmp/requirements
# copy our wheels from the build stage
# COPY --from=build /tmp/wheels /tmp/wheels

# combine build and ${STAGE}.txt - remove --no-binary to installing our own wheels
RUN --mount=type=bind,target=/tmp/wheels,source=/tmp/wheels,from=build \
    --mount=type=cache,mode=0755,target=/root/.cache/pip \
    du -shc /tmp/wheels \
    && ( cat /tmp/requirements/base.txt; sed -e 's/--no-binary.*//' -e 's/^-r .*//' /tmp/requirements/${STAGE}.txt ) | tee /tmp/requirements.txt >/dev/null \
    && pip install --find-links=/tmp/wheels -r /tmp/requirements.txt \
    && rm -rf /tmp/requirements /tmp/requirements.txt
# ---------------------------------------------
# END django image stage
# ---------------------------------------------

# ---------------------------------------------
# BEGIN production stage
# ---------------------------------------------
FROM django as django-production

# add our application
COPY --chown=django . /app

# copy the entrypoint and run scripts
RUN cp -ap /app/compose/django/entrypoint /entrypoint \
    && cp -vap /app/compose/django/start /start \
    && cp -vap /app/compose/django/queue/start /start-queue \
    && cp -vap /app/compose/django/seed_data /seed_data \
    && chmod -v 0755 /entrypoint /start /start-queue /seed_data \
    # remove all carriage returns in the case that a user checks out the files on a windows system
    # and has their git core.eol set to native or crlf
    && sed -i 's/\r$//g' /entrypoint /start /start-queue /seed_data \
    # due to volumes mounted to these locations we must created and set the ownership of the underlying directory
    # so that it is correctly propagated to the named volume
    && mkdir -p "/app/ghostwriter/media" "/app/staticfiles" \
    && chown -R "django": "/app/ghostwriter/media" "/app/staticfiles"
# ---------------------------------------------
# END production stage
# ---------------------------------------------

# ---------------------------------------------
# BEGIN local stage
# ---------------------------------------------
FROM django as django-local

# add our application
COPY --chown=django ./compose/django/entrypoint /entrypoint
COPY --chown=django ./compose/django/start-dev /start
COPY --chown=django ./compose/django/queue/start /start-queue
COPY --chown=django ./compose/django/seed_data /seed_data


# copy the entrypoint and run scripts
RUN chmod -v 0755 /entrypoint /start /start-queue /seed_data \
    # remove all carriage returns in the case that a user checks out the files on a windows system
    # and has their git core.eol set to native or crlf
    && sed -i 's/\r$//g' /entrypoint /start /start-queue /seed_data \
    # due to volumes mounted to these locations we must created and set the ownership of the underlying directory
    # so that it is correctly propagated to the named volume
    && mkdir -p "/app/ghostwriter/media" "/app/staticfiles" \
    && chown -R "django": "/app/ghostwriter/media" "/app/staticfiles"
# ---------------------------------------------
# END local stage
# ---------------------------------------------

# ---------------------------------------------
# BEGIN conditional stage
# with buildkit/bake only referenced stages will be built starting from this stage
# ---------------------------------------------
FROM django-${STAGE} as conditional

USER "django"

WORKDIR /app
# ---------------------------------------------
# END conditional stage
# ---------------------------------------------

# ---------------------------------------------
# BEGIN live stage
# ---------------------------------------------
FROM conditional as live

VOLUME ["/app/ghostwriter/media", "/app/staticfiles"]

ENTRYPOINT ["/entrypoint"]
# ---------------------------------------------
# END live stage
# ---------------------------------------------
