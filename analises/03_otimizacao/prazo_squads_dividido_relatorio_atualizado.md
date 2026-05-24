# Simulação por Squad com COMERCIAL dividido

Premissas:
- Squad 1 inicia em 09/03/2026
- Squads 2, 3, 4 e 5 iniciam em 01/04/2026
- Squad 1 faz BMC e COMPRAS; depois divide COMERCIAL com Squad 5
- Squad 2 faz MOPAR e depois RH
- Squad 3 faz CLIENTE e depois FINANCE
- Squad 4 faz SUPPLY CHAIN
- cada squad com 8 engenheiros e 2 analistas

## Resumo por squad

| Squad | Início | Fim | Lakes |
|---|---|---|---|
| Squad 1 | 09/03/2026 | 25/06/2026 | BMC -> COMPRAS -> COMERCIAL (dividido) |
| Squad 2 | 01/04/2026 | 28/08/2026 | MOPAR -> RH |
| Squad 3 | 01/04/2026 | 31/07/2026 | CLIENTE -> FINANCE |
| Squad 4 | 01/04/2026 | 11/08/2026 | SUPPLY CHAIN |
| Squad 5 | 01/04/2026 | 25/06/2026 | COMERCIAL (dividido) |

## Resumo por lake

| Squad | Lake | Histórias | Início | Fim | Prazo (corridos) |
|---|---|---:|---|---|---:|
| Squad 1 | BMC | 1 | 09/03/2026 | 26/03/2026 | 18 |
| Squad 1 | COMERCIAL (parcial) | 38 | 23/04/2026 | 25/06/2026 | 64 |
| Squad 1 | COMPRAS | 13 | 09/03/2026 | 22/04/2026 | 45 |
| Squad 1 + Squad 5 | COMERCIAL | 97 | 01/04/2026 | 25/06/2026 | 86 |
| Squad 2 | MOPAR | 39 | 01/04/2026 | 26/05/2026 | 56 |
| Squad 2 | RH | 72 | 27/05/2026 | 28/08/2026 | 94 |
| Squad 3 | CLIENTE | 42 | 01/04/2026 | 01/06/2026 | 62 |
| Squad 3 | FINANCE | 51 | 02/06/2026 | 31/07/2026 | 60 |
| Squad 4 | SUPPLY CHAIN | 85 | 01/04/2026 | 11/08/2026 | 133 |
| Squad 5 | COMERCIAL (parcial) | 59 | 01/04/2026 | 25/06/2026 | 86 |
