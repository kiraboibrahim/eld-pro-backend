# eld-pro

[![Build Status](https://travis-ci.org/kiraboibrahim/eld-pro.svg?branch=master)](https://travis-ci.org/kiraboibrahim/eld-pro)
[![Built with](https://img.shields.io/badge/Built_with-Cookiecutter_Django_Rest-F7B633.svg)](https://github.com/agconti/cookiecutter-django-rest)

A CMV simulation application that also creates Electronic Logging Device logs for the simulated trips in accoradance to the HOS regulations. Check out the project's [documentation](http://kiraboibrahim.github.io/eld-pro/).

# Prerequisites

- [Docker](https://docs.docker.com/docker-for-mac/install/)  

# Local Development

Start the dev server for local development:
```bash
docker-compose up
```

Run a command inside the docker container:

```bash
docker-compose run --rm web [command]
```
