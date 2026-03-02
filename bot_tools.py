import logging
import requests
from web3 import Web3
from solana.rpc.api import Client as SolanaClient
from solders.pubkey import Pubkey

# Connect to public RPC nodes (rate limits may apply, but works for testing)
# In production, these should be Infura/Alchemy or similar API keys.
# Using Ankr's public RPC as it is generally more stable than Cloudflare for eth_getBalance
eth_w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/eth'))
sol_client = SolanaClient("https://api.mainnet-beta.solana.com")

def get_eth_balance(address: str) -> str:
    """Fetches the real Ethereum balance for a given address."""
    try:
        checksum_address = Web3.to_checksum_address(address)
        balance_wei = eth_w3.eth.get_balance(checksum_address)
        balance_eth = eth_w3.from_wei(balance_wei, 'ether')
        return f"{balance_eth:.4f} ETH"
    except Exception as e:
        logging.error(f"Error fetching ETH balance: {e}")
        return "Error fetching ETH balance"

def get_sol_balance(address: str) -> str:
    """Fetches the real Solana balance for a given address."""
    try:
        pubkey = Pubkey.from_string(address)
        response = sol_client.get_balance(pubkey)
        # Solana balance is returned in lamports (1 SOL = 1,000,000,000 lamports)
        if hasattr(response, 'value'):
            lamports = response.value
            return f"{(lamports / 1_000_000_000):.4f} SOL"
        else:
            return "Error parsing SOL balance"
    except Exception as e:
        logging.error(f"Error fetching SOL balance: {e}")
        return "Error fetching SOL balance"

import os
from dotenv import load_dotenv

# Ensure we load env vars so we can get the DFLOW_API_KEY
load_dotenv()
DFLOW_API_KEY = os.getenv("DFLOW_API_KEY", "")

def get_kalshi_markets() -> str:
    """Fetches popular/recent markets from Kalshi via DFlow API."""
    try:
        # Use the real DFlow API endpoint provided by the user's documentation
        # Base URL: https://a.prediction-markets-api.dflow.net
        url = "https://a.prediction-markets-api.dflow.net/api/v1/events" 
        headers = {
            "x-api-key": DFLOW_API_KEY,
            "Content-Type": "application/json"
        }
        
        params = {
            "withNestedMarkets": "true",
            "status": "active",
            "limit": 5
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            events = data.get("events", [])
            
            if not events:
                return "No active events found on DFlow right now."
                
            market_summaries = ["Here are some active markets:"]
            for event in events:
                ticker = event.get("ticker", "Unknown")
                title = event.get("title", "No Title")
                subtitle = event.get("subtitle", "")
                
                market_summaries.append(f"\nEvent: {title} ({ticker})")
                if subtitle:
                    market_summaries.append(f"  Info: {subtitle}")
                
                markets = event.get("markets", [])
                for idx, market in enumerate(markets):
                    m_title = market.get("title", f"Option {idx+1}")
                    
                    yes_ask = market.get("yesAsk")
                    no_ask = market.get("noAsk")
                    
                    odds_str = ""
                    if yes_ask is not None and no_ask is not None:
                        try:
                            # Convert string "0.450" to 45¢
                            yes_cents = int(float(yes_ask) * 100)
                            no_cents = int(float(no_ask) * 100)
                            odds_str = f" [Odds: YES @ {yes_cents}¢ | NO @ {no_cents}¢]"
                        except ValueError:
                            pass
                    
                    market_summaries.append(f"  - Market: {m_title}{odds_str}")
                
            return "\n".join(market_summaries)

        else:
            return f"Failed to fetch DFlow events. API returned HTTP {response.status_code}: {response.text}"
        
    except Exception as e:
        logging.error(f"Error fetching Kalshi Dflow markets: {e}")
        return "Error fetching Kalshi markets."



def execute_mock_trade(market: str, prediction: str, amount: str, address: str) -> str:
    """Simulates executing a trade on a prediction market after checking balances."""
    
    # Try fetching real balance for the target address first.
    # We'll use get_sol_balance as DFlow markets are on Solana.
    balance_str = get_sol_balance(address)
    
    # Check if the balance is effectively 0
    if "0.0000 SOL" in balance_str or "Error" in balance_str:
        return f"CRITICAL: Trade execution rejected. The wallet ({address}) has an insufficient balance of {balance_str}. Please deposit funds to execute this trade."
        
    return f"SUCCESS: Order filled! Bought {amount} of {prediction} on market {market}."


# Define the Tool JSON Schema expected by OpenAI API
llm_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_eth_balance",
            "description": "Get the current Ethereum (ETH) balance of a wallet address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The Ethereum public wallet address starting with 0x"
                    }
                },
                "required": ["address"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sol_balance",
            "description": "Get the current Solana (SOL) balance of a wallet address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The Solana public wallet address (base58 encoded)"
                    }
                },
                "required": ["address"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_kalshi_markets",
            "description": "Fetch the latest, popular open prediction markets from Kalshi.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_trade",
            "description": "Execute a trade on a prediction market. Call this only when the user explicitly asks to trade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "description": "The prediction market name or ticker (e.g. BTC_PRICE, ELECTION_2028)"
                    },
                    "prediction": {
                        "type": "string",
                        "description": "The predicted outcome (e.g. UP, DOWN, YES, NO)"
                    },
                    "amount": {
                        "type": "string",
                        "description": "The amount to trade (e.g. 5, 10.5)"
                    },
                    "address": {
                        "type": "string",
                        "description": "The user's Solana wallet address to trade from"
                    }
                },
                "required": ["market", "prediction", "amount", "address"],
            },
        }
    }
]

# Map names to actual python functions
available_functions = {
    "get_eth_balance": get_eth_balance,
    "get_sol_balance": get_sol_balance,
    "get_kalshi_markets": get_kalshi_markets,
    "execute_trade": execute_mock_trade,
}

