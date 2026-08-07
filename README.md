# python-templates

[![Template][template-shield]][template-link]
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-black.json)](https://github.com/copier-org/copier)
[![Python][python-shield]][python-org]
[![uv][uv-shield]][uv-repo]
[![Jinja][jinja-shield]][jinja-repo]
[![Docker][docker-shield]][docker-repo]
[![License][license-shield]][license-link]

This repository contains a Copier template for creating new Python-based projects with an optional backend, frontend, and background job worker.

Use this template when you want a consistent starting point for a new application and want Copier to generate the repository structure, configuration, and starter files from a small set of answers.

## What this template generates

By default, Copier renders a project with:

- A Python backend service
- A Vue 3 + Vite frontend
- Optional background job worker support
- Dockerfiles for the selected components
- A Docker Compose file for local development
- Docs scaffolding
- Shared linting and formatting configuration

You can enable or disable the backend, frontend, and job worker independently during generation.

## Prerequisites

Install Copier and the Jinja extensions used by this template in the same environment:

```bash
uv tool install --with jinja2-time --with jinja2-slug --with jinja-markdown copier
```

You also need:

- `git`
- `uv` for the Python parts
- `node` and `npm` for the frontend parts

## Create a new project

Run Copier from the root of this template repository:

```bash
copier copy . ../my-new-project
```

You will be prompted for the project name and the component options. Copier then creates the target repository and writes the rendered files there.

If you want to use this template directly from Git instead of a local checkout, you can also copy from the repository URL:

```bash
copier copy https://github.com/it-at-m/python-templates.git ../my-new-project
```

## Answers you will be asked for

The template is driven by the values in [copier.yml](copier.yml):

- `project_name`: Name of the generated repository or application
- `module_name`: Python import package name, derived from `project_name` by default
- `repository_owner`: GitHub owner used in generated URLs and metadata
- `short_description`: Short summary shown in the generated README and docs
- `maintainers`: GitHub usernames of the maintainers as a YAML list
- `backend`: Enable or disable the backend service
- `frontend`: Enable or disable the Vue frontend
- `job`: Enable or disable the background job worker
- `backend_ubi10_base_image`: Base image for the backend container when the backend is enabled
- `job_ubi10_base_image`: Base image for the job container when the job worker is enabled
- `oci_authors`, `oci_vendor`, `oci_license`: OCI metadata values used in generated container images

The defaults are chosen so that a standard project can be created quickly, but you can override any of them during generation.

## Typical workflow after generation

After Copier finishes, switch into the new repository and install the dependencies for the parts you enabled.

Backend:

```bash
cd my-new-project/my-new-project-backend
uv sync
uv run python main.py
```

Frontend:

```bash
cd my-new-project/my-new-project-frontend
npm install
npm run dev
```

Job worker:

```bash
cd my-new-project/my-new-project-job
uv sync
uv run python main.py
```

If the generated repository includes Docker Compose, you can usually start the selected services from the repository root with:

```bash
docker compose up --build
```

## Updating an existing project

Copier is not only for first-time generation. After the template evolves, you can refresh a generated repository with:

```bash
copier update
```

Run that command from the generated repository root. Copier uses the stored answers file to compare the template version that was originally used with the current template.

## Template structure

The top-level template repository is organized like this:

- [README.md.jinja](README.md.jinja) renders the README for generated projects
- [copier.yml](copier.yml) defines the template questions and defaults
- [compose.yaml.jinja](compose.yaml.jinja) renders the local compose file
- `{{project_name}}-backend/` contains the backend scaffold
- `{{project_name}}-frontend/` contains the frontend scaffold
- `{{project_name}}-job/` contains the job worker scaffold
- `docs/` contains the generated documentation site content

Files ending in `.jinja` are rendered by Copier into the target repository. The root README in this repository documents the template itself; the generated project README is produced from [README.md.jinja](README.md.jinja).

## How the component selection works

The backend, frontend, and job worker are rendered conditionally:

- If `backend` is disabled, the backend directory and its Docker setup are excluded
- If `frontend` is disabled, the frontend directory and its Docker setup are excluded
- If `job` is disabled, the job worker directory and its Docker setup are excluded

This lets you keep the generated project small when you do not need all components.

## Customizing the template

If you are maintaining this template, update the Jinja source files rather than the rendered output.

- Edit the `.jinja` files to change what future projects receive
- Adjust [copier.yml](copier.yml) when you want to add, remove, or rename template answers
- Use the `when` and `_exclude` rules in [copier.yml](copier.yml) to control conditional files
- Keep the generated-project README in [README.md.jinja](README.md.jinja) aligned with the template behavior

When you change the template, create a fresh test project and run `copier update` there to verify the rendered result.

## Troubleshooting

If Copier fails while rendering Jinja templates, make sure the `copier` tool and the required Jinja extensions are installed in the same environment.

If the generated backend or job project does not start, check that the selected UBI base image is compatible with your runtime and that the rendered container configuration matches the chosen components.

If a directory is unexpectedly missing, review the `backend`, `frontend`, and `job` answers and the `_exclude` rules in [copier.yml](copier.yml).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community guidelines.

<!-- badges / links -->

[template-shield]: https://img.shields.io/badge/template-Copier-111111?logo=copier
[template-link]: https://copier.readthedocs.io/
[python-shield]: https://img.shields.io/badge/python-3.14.4%2B-3776AB?logo=python&logoColor=white
[python-org]: https://www.python.org/
[uv-shield]: https://img.shields.io/badge/uv-tool-111111?logo=astral&logoColor=white
[uv-repo]: https://docs.astral.sh/uv/
[jinja-shield]: https://img.shields.io/badge/jinja-templates-B41717?logo=jinja&logoColor=white
[jinja-repo]: https://jinja.palletsprojects.com/
[docker-shield]: https://img.shields.io/badge/docker-supported-2496ED?logo=docker&logoColor=white
[docker-repo]: https://www.docker.com/
[license-shield]: https://img.shields.io/badge/license-MIT-007EC6
[license-link]: LICENSE
