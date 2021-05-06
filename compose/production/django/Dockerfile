FROM python:3.8-alpine

ENV PYTHONUNBUFFERED 1

ENV PYTHONPATH="$PYTHONPATH:/app/config"

RUN addgroup -S django \
    && adduser -S -G django django

# Requirements are installed here to ensure they will be cached.
COPY ./requirements /requirements
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
    # Rust and Cargo required by the ``cryptography`` Python package
    && apk add --no-cache rust \
    && apk add --no-cache cargo \
    && pip install --no-cache-dir -r /requirements/production.txt \
    && rm -rf /requirements \
    # remove the virtual package group 'build-deps'
    && apk del build-deps \
    && rm -rf /var/cache/apk/*

COPY --chown=django . /app
# COPY --chmod=0755 --chown=django ./compose/production/django/entrypoint /entrypoint
# COPY --chmod=0755 --chown=django ./compose/production/django/start /start
# COPY --chmod=0755 --chown=django ./compose/production/django/queue/start /start-queue
# COPY --chmod=0755 --chown=django ./compose/production/django/seed_data /seed_data

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
