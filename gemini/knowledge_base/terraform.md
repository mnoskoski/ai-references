# Padrão para Módulo Terraform de Bucket S3

Este documento descreve o padrão oficial da empresa para criar um módulo de bucket S3 no Terraform.

## Estrutura do Módulo

O módulo sempre deve os seguintes arquivos:
- `main.tf`: Define o recurso `aws_s3_bucket` e outros recursos relacionados.
- `variables.tf`: Declara as variáveis de entrada.
- `outputs.tf`: Declara os outputs do módulo.
- `anotacoes.txt`: arquivo usado para documentacao e anotações necessárias.

## Conteúdo do main.tf

O `main.tf` deve sempre incluir bloqueio de acesso público, versionamento e logging.

**Código de Exemplo:**

\`\`\`hcl
resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
  # Nossas tags padronizadas são essenciais
  tags = merge(
    var.tags,
    {
      "ManagedBy"   = "Terraform"
      "Project"     = var.project_name
      "Environment" = var.environment
    }
  )
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "this" {
  count = var.logging_bucket_name != "" ? 1 : 0

  bucket = aws_s3_bucket.this.id

  target_bucket = var.logging_bucket_name
  target_prefix = "log/${var.bucket_name}/"
}
\`\`\`

## Variáveis Obrigatórias

As seguintes variáveis devem estar presentes em `variables.tf`:
- `bucket_name`: string
- `project_name`: string
- `environment`: string
- `logging_bucket_name`: string (pode ser vazia para desabilitar logging)
- `tags`: map(string)