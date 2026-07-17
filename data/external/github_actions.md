# GitHub Actions

## Ejemplo
```yaml
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm test
```

## Secrets
```yaml
jobs:
  deploy:
    steps:
      - run: echo "${{ secrets.MY_SECRET }}"
```
