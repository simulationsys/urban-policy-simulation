# Contributing

Thanks for your interest in contributing to Urban Policy Simulation!

## Development Workflow

1. **Fork & branch.** Create a feature branch off `dev` (directly pushing to `main` is strictly prohibited, all work must target `dev` as defined in `rule.md`):
   `git checkout -b feat/short-description dev`.
2. **Set up the environment.** Copy `.env.example` to `.env` and run
   `docker-compose up --build`.
3. **Make focused changes.** Keep pull requests scoped to a single concern.
4. **Test.** Add or update tests and make sure the existing suite passes.
5. **Open a PR.** Describe the change, link related issues, and request review.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` a new feature
- `fix:` a bug fix
- `docs:` documentation only
- `refactor:` code change that neither fixes a bug nor adds a feature
- `test:` adding or correcting tests
- `chore:` tooling, build, or maintenance

## Code Style

- Follow the linter/formatter configured in each service directory.
- Prefer small, well-named functions and meaningful tests over comments.

## Reporting Issues

Open a GitHub issue with steps to reproduce, expected vs. actual behavior, and
environment details. Security-sensitive reports should be sent privately to the
maintainers rather than filed publicly.
