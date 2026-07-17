# GitLab CI

## Ejemplo
```yaml
stages:
  - build
  - test

build:
  stage: build
  image: node:20
  script:
    - npm ci
    - npm run build
```
