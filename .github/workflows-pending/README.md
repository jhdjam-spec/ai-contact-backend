# CI/CD workflow (ожидает включения)

Файл [ci.yml.txt](ci.yml.txt) — это готовый GitHub Actions пайплайн
(lint + test + build + deploy). Он временно лежит здесь как `.txt`, потому что
первый push делался токеном без scope `workflow`.

## Как включить

1. Переименуйте `.github/workflows-pending/ci.yml.txt` в
   `.github/workflows/ci.yml` (через веб-интерфейс GitHub или локально с токеном,
   имеющим scope `workflow`: `gh auth refresh -s workflow`).
2. Задайте секрет `RENDER_DEPLOY_HOOK` (см. docs/ci-cd.md) для стадии деплоя.
