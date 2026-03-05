# Contributing to RiskFeed Agentic Chatbot

Thanks for helping build the RiskFeed agentic chatbot.

This project is intentionally small and focused. Please keep changes aligned with the **scope rules** in `README.md`.

## Getting started

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create and activate a virtual environment.
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Run the test suite (once tests exist):

   ```bash
   pytest
   ```

## Branches and pull requests

- Create a feature branch from `main`.
- Keep PRs small and focused (one logical change).
- Update or add tests for any behavior change.

## Coding guidelines (high level)

- Follow the **project goals and guardrails** in `README.md`.
- Prefer deterministic behavior in tests (no external network calls, seeded randomness).
- Keep public APIs (especially `/chat`) backward compatible whenever possible.

## Commit messages

- Use clear, descriptive messages:
  - Good: `add basic health endpoint`
  - Good: `implement project draft tool schema`
  - Avoid: `fix stuff`, `wip`

## Questions

If you are unsure whether a change fits the scope:

- Open a GitHub issue first, or
- Start your PR as a “Draft” and describe the design briefly.

