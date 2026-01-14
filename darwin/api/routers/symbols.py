"""
Symbols router for Darwin API.

Provides endpoints for listing available trading symbols/tickers.
"""

from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SymbolInfo(BaseModel):
    """Symbol information."""

    symbol: str
    name: str
    venue: str


class SymbolsListResponse(BaseModel):
    """Response for symbols list."""

    symbols: List[SymbolInfo]


@router.get("/", response_model=SymbolsListResponse)
async def list_symbols():
    """
    List all available trading symbols.

    Returns symbols that have been explicitly made available within the platform.
    To add new symbols, update this list in the backend.

    Returns:
        SymbolsListResponse: List of available symbols
    """
    symbols = [
        SymbolInfo(
            symbol="BTC-USD",
            name="Bitcoin",
            venue="coinbase"
        ),
        SymbolInfo(
            symbol="ETH-USD",
            name="Ethereum",
            venue="coinbase"
        ),
        SymbolInfo(
            symbol="SOL-USD",
            name="Solana",
            venue="coinbase"
        ),
    ]

    return SymbolsListResponse(symbols=symbols)
