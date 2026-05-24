# Timeline do Projeto (Gantt)

## 1) Cenário atual — COMERCIAL dividido entre Squad 1 e Squad 5

```mermaid
gantt
    title Projeto - Cenário Atual (fim em 28/08/2026)
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m

    section Squad 1
    BMC                      : 2026-03-09, 2026-03-26
    COMPRAS                  : 2026-03-09, 2026-04-22
    COMERCIAL (parcial)      : 2026-04-23, 2026-07-06

    section Squad 2
    MOPAR                    : 2026-04-01, 2026-05-26
    RH                       : 2026-05-27, 2026-08-28

    section Squad 3
    CLIENTE                  : 2026-04-01, 2026-06-01
    FINANCE                  : 2026-06-02, 2026-07-31

    section Squad 4
    SUPPLY CHAIN             : 2026-04-01, 2026-08-11

    section Squad 5
    COMERCIAL (parcial)      : 2026-04-01, 2026-06-23

    section Marco
    Fim do Projeto (Atual)   : milestone, 2026-08-28, 1d
```

## 2) Cenário otimizado — menor prazo encontrado

Premissa vencedora:

- COMERCIAL dividido (Squad 1 + Squad 5)
- depois Squad 1 ajuda SUPPLY CHAIN
- depois Squad 5 ajuda RH

```mermaid
gantt
    title Projeto - Cenário Otimizado (fim em 31/07/2026)
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m

    section Frentes principais
    COMERCIAL (dividido)         : 2026-04-01, 2026-07-06
    SUPPLY CHAIN (com ajuda S1)  : 2026-04-01, 2026-07-24
    RH (com ajuda S5)            : 2026-05-27, 2026-07-28
    FINANCE                      : 2026-06-02, 2026-07-31

    section Marco
    Fim do Projeto (Otimizado)   : milestone, 2026-07-31, 1d
```
