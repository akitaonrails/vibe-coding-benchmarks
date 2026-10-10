FROM ruby:3.4.9-slim@sha256:756f37e6d559e7a081ff430be227efdce614047d8c7498a5795480545421b2fe AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libyaml-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY Gemfile Gemfile.lock ./
ENV BUNDLE_FROZEN=true BUNDLE_JOBS=2
RUN bundle install
FROM ruby:3.4.9-slim@sha256:756f37e6d559e7a081ff430be227efdce614047d8c7498a5795480545421b2fe
WORKDIR /app
COPY --from=build /usr/local/bundle /usr/local/bundle
COPY . .
ENV BUNDLE_FROZEN=true RAILS_ENV=production HOME=/tmp TMPDIR=/tmp
USER 65534:65534
ENTRYPOINT ["ruby", "/app/main.rb"]
