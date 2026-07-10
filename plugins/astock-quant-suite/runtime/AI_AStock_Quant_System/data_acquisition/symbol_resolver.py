from __future__ import annotations


class SymbolResolver:
    SYMBOLS = {
        "中国神华": ("601088.SH", "stock"),
        "神华": ("601088.SH", "stock"),
        "工商银行": ("601398.SH", "stock"),
        "建设银行": ("601939.SH", "stock"),
        "农业银行": ("601288.SH", "stock"),
        "红利ETF": ("510880.SH", "etf"),
        "银行ETF": ("512800.SH", "etf"),
        "沪深300": ("000300.SH", "index"),
        "上证指数": ("000001.SH", "index"),
    }
    CRYPTO_ALIASES = {
        "BTC": "BTCUSDT",
        "比特币": "BTCUSDT",
        "ETH": "ETHUSDT",
        "以太坊": "ETHUSDT",
        "USDT": "USDT",
        "币安": "crypto_exchange",
        "合约": "crypto_derivative",
        "数字货币": "crypto",
        "加密货币": "crypto",
    }

    def resolve(self, text_or_symbol: str) -> tuple[str, str]:
        value = text_or_symbol.strip()
        unsupported = self.detect_unsupported_asset(value)
        if unsupported:
            raise ValueError(
                f"检测到非 A 股标的/市场：{unsupported}。当前 astock-quant-research 只支持 A 股/ETF/指数；数字货币版本需要单独工作流，不能混用 QMT/A股回测假设。"
            )
        if value.endswith((".SH", ".SZ")):
            return value, self.asset_type(value)
        for name, item in self.SYMBOLS.items():
            if name in value:
                return item
        raise ValueError(f"无法识别标的：{text_or_symbol}")

    def detect_unsupported_asset(self, text_or_symbol: str) -> str:
        value = text_or_symbol.strip()
        upper = value.upper()
        for alias, normalized in self.CRYPTO_ALIASES.items():
            if alias.upper() in upper or alias in value:
                return normalized
        if "/" in upper and any(base in upper for base in ["BTC", "ETH", "USDT", "USDC"]):
            return upper
        if upper.endswith(("USDT", "USDC")) and any(upper.startswith(base) for base in ["BTC", "ETH", "SOL", "BNB", "DOGE"]):
            return upper
        return ""

    def asset_type(self, symbol: str) -> str:
        if symbol.startswith(("51", "15", "56")):
            return "etf"
        if symbol.startswith(("000", "399")) and symbol.endswith((".SH", ".SZ")):
            return "index"
        return "stock"
