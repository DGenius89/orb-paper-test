# ORB paper-test

Test of de opening-range-breakout uit de
[day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT) echt iets oplevert.
Zelfde regel als de skill, maar eerlijk gemeten: met kosten, over 40 aandelen, en live op een
**Alpaca paper-account** (nepgeld). De code praat alleen met `paper-api.alpaca.markets` en kan
niet live handelen.

## De regel
- Opening range: 09:30–09:45 ET. Instap: eerste 5-min close boven de range-high (uiterlijk 15:30).
- Stop: midden van de range. Doel: 1R. Alles dicht om 15:55 ET.
- $50 max verlies per trade, max $4.000 per order, max 3 trades en $150 verlies per dag.
- Slippage-schatting: 3 bps per kant (paper-fills zijn te optimistisch).

## Wat er draait (GitHub Actions)
| workflow | wanneer | doet |
|---|---|---|
| `backtest` | handmatig | 12 maanden, 40 aandelen, in- vs out-of-sample, vs SPY → `backtest/` |
| `live-paper` | elke 30 min tijdens de beurs | scant, plaatst bracket-orders op paper, sluit 15:55 ET |
| `daily-report` | 22:40 NL-tijd | trades, equity, schaduw-backtest, SPY → `paper-log/SUMMARY.md` |

## Setup
1. Alpaca paper-account, reset het paper-saldo naar $5.000, maak **paper** API-keys.
2. Repo → Settings → Secrets and variables → Actions: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`.
3. Actions → `backtest` → Run workflow.

## Spelregels voor de evaluatie
- Geen strategiewijzigingen vóór 50 live trades. Eerder bijsturen = ruis optimaliseren.
- Stopcriteria na 100 trades of 3 maanden: netto winst na slippage **en** beter dan SPY
  kopen-en-houden over dezelfde periode. Zo niet: stoppen.

## Variant: stocks in play (vooraf vastgelegd, 11 nov 2026)
Selectie per dag zonder vooruitkijken: gap-up ≥ 2 % op de open, koers ≥ $5, gem. volume ≥ 1M;
de 50 grootste gappers, daarvan top 20 op relatief volume in de eerste 15 minuten. Verder
identieke regels en kosten. Uitkomst basisversie: netto −$2.253 over 756 trades vs SPY +$537.

**Criterium:** PASS alleen als het out-of-sample deel netto winstgevend is **én** het hele
jaar netto beter is dan SPY kopen-en-houden. FAIL = stoppen, geen extra tweak-rondes op
dezelfde data.
