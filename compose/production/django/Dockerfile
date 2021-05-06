FROM python:3.8-alpine as base

# only update build base when requirements have changed
COPY ./requirements /requirements
# install build dependencies
RUN apk update \
    && apk add --no-cache build-base
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
    && pip install --no-cache-dir -r /requirements/production.txt \
    # build wheels
    && pip install wheel && pip wheel --wheel-dir=/tmp/wheels -r /requirements/production.txt \
    # remove the virtual package group 'build-deps'
    && apk del build-deps

# begin container image
FROM python:3.8-alpine

# stream python output for django logs
ENV PYTHONUNBUFFERED 1

ENV PYTHONPATH="$PYTHONPATH:/app/config"

RUN addgroup -S django \
    && adduser -S -G django django

# install runtime dependencies.  `add --no-cache` performs an apk update, adds packages and excludes caching
# in order to not require deletion of apk cache.
RUN apk add --no-cache postgresql-dev \
    # Pillow dependencies
    jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev \
    # CFFI dependencies
    libffi-dev py-cffi \
    # XLSX dependencies
    libxml2-dev libxslt-dev

# ensure that we are using the same requirements from the base stage
COPY --from=base /requirements /requirements
# copy our wheels from the base stage
COPY --from=base /tmp/wheels /tmp/wheels

# combine base and production.txt - remove --no-binary to installing our own wheels
RUN ( cat requirements/base.txt; sed -e 's/--no-binary.*//' -e 's/^-r .*//' requirements/production.txt ) | tee /tmp/requirements.txt >/dev/null \
    && pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r /tmp/requirements.txt \
    && rm -rf /requirements /tmp/requirements.txt

# add our application
COPY --chown=django . /app

# copy the entrypoint and run scripts
RUN cp -ap /app/compose/production/django/entrypoint /entrypoint \
    && cp -vap /app/compose/production/django/start /start \
    && cp -vap /app/compose/production/django/queue/start /start-queue \
    && cp -vap /app/compose/production/django/seed_data /seed_data \
    && chmod -v 0755 /entrypoint /start /start-queue /seed_data \
    # remove all carriage returns in the case that a user checks out the files on a windows system
    # and has their git core.eol set to native or crlf
    && sed -i 's/\r$//g' /entrypoint /start /start-queue /seed_data \
    # due to volumes mounted to these locations we must created and set the ownership of the underlying directory
    # so that it is correctly propagated to the named volume
    && mkdir -p "/app/ghostwriter/media" "/app/staticfiles" \
    && chown django: "/app/ghostwriter/media" "/app/staticfiles"

USER django

WORKDIR /app

VOLUME ["/app/ghostwriter/media", "/app/staticfiles"]

ENTRYPOINT ["/entrypoint"]
