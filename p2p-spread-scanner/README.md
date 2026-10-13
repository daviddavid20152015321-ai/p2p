# P2P Spread Scanner — Telegram Mini App starter

A runnable MVP scaffold: React + TypeScript frontend, FastAPI backend, net-spread calculator, filters, and Telegram WebApp integration. The included feed is **clearly labeled demo data**; it does not claim to show live exchange quotes.

## Requirements
- Node.js 20+
- Python 3.11+

## Run locally

### Backend
```bash
cd backend
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### Frontend
In another terminal:
```bash
cd frontend
npm install
npm run dev
```
Vite normally serves at http://localhost:5173. The frontend proxies `/api` to the backend.

## What works in this starter
- Dark, responsive scanner dashboard
- Asset / fiat / capital / fee filters
- Net spread and estimated profit calculations
- Sortable opportunities and manual refresh
- Telegram WebApp SDK initialization when opened inside Telegram
- FastAPI endpoint and typed API response

## Live data integration — important
The current provider is intentionally a demo provider. Before presenting opportunities as live, connect a permitted, documented source and display its timestamp, order limits, payment method, advertiser completion rate, and remaining quantity. Exchange API access differs by exchange and account eligibility. For example, Bybit documents its P2P ads endpoint and notes that P2P API access has advertiser eligibility requirements:
- https://bybit-exchange.github.io/docs/p2p/ad/online-ad-list
- https://bybit-exchange.github.io/docs/p2p/guide

Do not assume that a public website endpoint is a supported API. Check the exchange's current terms and API requirements before integration. Never put exchange API secrets in the frontend. If credentials are needed, keep them in backend environment variables and use read-only permissions where possible.

## Calculation model
The calculator assumes:
- buy price = price at which the user can buy crypto from an advertiser;
- sell price = price at which the user can sell crypto to an advertiser;
- estimated crypto quantity = capital / buy price;
- gross profit = quantity × (sell price − buy price);
- estimated net profit = gross profit minus the configured fee estimate;
- net spread % = estimated net profit / capital × 100.

This is an estimate, not a guaranteed execution price. Actual results depend on order limits, payment methods, liquidity, changing ads, transfer costs, fees, and whether the user can complete both legs.

## Telegram deployment checklist
1. Deploy the frontend and backend to HTTPS hosting.
2. Configure the frontend API URL for your deployment.
3. Create a bot using Telegram's official `@BotFather`.
4. Set the Mini App URL in BotFather.
5. Set allowed origins, rate limits, monitoring, and secrets on the backend.
6. Validate Telegram `initData` on the backend before trusting user identity. The starter initializes the client SDK but does not yet perform server-side `initData` authentication.
