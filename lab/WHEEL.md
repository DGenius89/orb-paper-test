# "The wheel" (puts verkopen → covered calls): vooraf vastgelegd (12 nov 2026, vóór de test)

Bron: video van een creator die "rond 35% elk jaar" claimt met de wheel.

## Waarom een index als maatstaf
De wheel = cash-secured puts verkopen; bij toewijzing aandelen houden en covered calls verkopen.
Door put-call-pariteit heeft een cash-secured put hetzelfde uitbetalingsprofiel als een covered
call met dezelfde strike. Op de S&P 500 wordt de wheel dus nauwkeurig benaderd door twee
officiële, dagelijks gepubliceerde Cboe-indexen, inclusief echte optieprijzen:
- **PUT** (Cboe S&P 500 PutWrite): elke maand een at-the-money put verkopen, volledig gedekt
  door T-bills. Dit is de "cash"-kant van de wheel.
- **BXM** (Cboe S&P 500 BuyWrite): S&P 500 houden en elke maand een at-the-money call verkopen.
  Dit is de "aandelen"-kant.
Een wheel op losse aandelen voegt daar stock-picking- en concentratierisico aan toe; dat kan
zonder historische optieprijzen per aandeel niet eerlijk getest worden (Alpaca heeft
optiedata pas vanaf 2024).

## Data
- Cboe dagwaarden PUT, BXM en SPX (prijsindex, zonder dividend) vanaf de start van de reeksen.
- SPY total return (Alpaca, `adjustment=all`) vanaf 2016 als eerlijke benchmark mét dividend.

## Wat wordt gemeten
- Rendement per kalenderjaar, CAGR, volatiliteit, Sharpe (zonder risicovrije rente), maximale daling.
- 2008, 2020 en 2022 apart.

## Oordeel over de claim
- **"35% per jaar, elk jaar"** houdt stand als PUT of BXM in elk jaar ≥ 35% haalt. Faalt als
  er jaren onder 0 % zijn of de CAGR ver onder 35% ligt.
- **Is de wheel beter dan kopen-en-houden?** Ter info: Sharpe en maximale daling van PUT/BXM
  tegenover S&P (SPY total return vanaf 2016; SPX prijs over de volledige historie, wat de
  S&P ~2%/jr benadeelt).
Geen parameters om te fitten, dus geen hold-out nodig: de indexregels liggen bij Cboe vast.
