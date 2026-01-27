# -*- coding: utf-8 -*-
"""
Legacy Data Service for 185.222 exported data
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

from app.config import get_settings, LEGACY_FILES

logger = logging.getLogger(__name__)


class LegacyDataService:
    """Service for working with legacy JSON data from 185.222"""

    def __init__(self):
        self.settings = get_settings()
        self._client_cars_mapping: Dict[str, List[str]] = {}
        self._order_history: Dict[str, List[dict]] = {}
        self._order_details: Dict[str, dict] = {}
        self._loaded = False

    def _get_file_path(self, file_key: str) -> Path:
        """Get full path to legacy data file"""
        filename = LEGACY_FILES.get(file_key, file_key)
        # Check in data dir first, then in root
        data_path = self.settings.DATA_DIR / filename
        if data_path.exists():
            return data_path
        root_path = self.settings.BASE_DIR / filename
        if root_path.exists():
            return root_path
        return data_path

    def load_data(self) -> None:
        """Load all legacy data files"""
        if self._loaded:
            return

        # Load client-car mapping
        mapping_path = self._get_file_path("client_cars_mapping")
        if mapping_path.exists():
            with open(mapping_path, "r", encoding="utf-8") as f:
                self._client_cars_mapping = json.load(f)
            logger.info(f"Loaded client-car mapping: {len(self._client_cars_mapping)} clients")

        # Load order history
        history_path = self._get_file_path("order_history")
        if history_path.exists():
            with open(history_path, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                # Convert list to dict by client_code
                self._order_history = {
                    item["client_code"]: item["orders"]
                    for item in history_data
                    if "client_code" in item
                }
            total_orders = sum(len(orders) for orders in self._order_history.values())
            logger.info(f"Loaded order history: {len(self._order_history)} clients, {total_orders} orders")

        # Load order details
        details_path = self._get_file_path("order_details")
        if details_path.exists():
            with open(details_path, "r", encoding="utf-8") as f:
                self._order_details = json.load(f)
            logger.info(f"Loaded order details: {len(self._order_details)} orders")

        self._loaded = True

    # ==================== Client Cars ====================

    def get_client_cars(self, client_ref: str) -> List[str]:
        """
        Get car Ref_Keys for a client from legacy mapping.

        Args:
            client_ref: Client Ref_Key

        Returns:
            List of car Ref_Keys
        """
        self.load_data()
        return self._client_cars_mapping.get(client_ref, [])

    def get_all_client_car_mappings(self) -> Dict[str, List[str]]:
        """Get all client-car mappings"""
        self.load_data()
        return self._client_cars_mapping

    # ==================== Order History ====================

    def get_client_order_history(self, client_code: str) -> List[dict]:
        """
        Get order history for a client from legacy data.

        Args:
            client_code: Client Code (not Ref_Key!)

        Returns:
            List of historical orders with date, sum, car_name, etc.
        """
        self.load_data()
        return self._order_history.get(client_code, [])

    def get_order_details(self, order_number: str) -> Optional[dict]:
        """
        Get detailed info (works, parts) for a legacy order.

        Args:
            order_number: Order Number

        Returns:
            Dict with 'works' and 'goods' arrays, or None
        """
        self.load_data()
        return self._order_details.get(order_number)

    def find_order_by_number(self, order_number: str, client_code: str = None) -> Optional[dict]:
        """
        Find order header info (date, car_name, sum) by order number.

        Args:
            order_number: Order Number
            client_code: Optional client code to filter by (handles duplicates)

        Returns:
            Dict with order header info including client_code, or None
        """
        self.load_data()

        # If client_code provided, search only in that client's orders
        if client_code:
            orders = self._order_history.get(client_code, [])
            for order in orders:
                if order.get("number") == order_number:
                    result = order.copy()
                    result["client_code"] = client_code
                    return result

        # Otherwise search all (returns first match)
        for code, orders in self._order_history.items():
            for order in orders:
                if order.get("number") == order_number:
                    result = order.copy()
                    result["client_code"] = code
                    return result
        return None

    def search_order_history(
        self,
        client_code: str = None,
        date_from: str = None,
        date_to: str = None,
        limit: int = 50,
    ) -> List[dict]:
        """
        Search order history with filters.

        Args:
            client_code: Filter by client code
            date_from: Filter by date (YYYY-MM-DD)
            date_to: Filter by date (YYYY-MM-DD)
            limit: Max results

        Returns:
            List of matching orders
        """
        self.load_data()
        results = []

        if client_code:
            # Search for specific client
            orders = self._order_history.get(client_code, [])
            for order in orders:
                order_copy = order.copy()
                order_copy["client_code"] = client_code
                results.append(order_copy)
        else:
            # Search all
            for code, orders in self._order_history.items():
                for order in orders:
                    order_copy = order.copy()
                    order_copy["client_code"] = code
                    results.append(order_copy)

        # Apply date filters
        if date_from:
            results = [o for o in results if o.get("date", "") >= date_from]
        if date_to:
            results = [o for o in results if o.get("date", "") <= date_to]

        # Sort by date descending
        results.sort(key=lambda x: x.get("date", ""), reverse=True)

        return results[:limit]

    # ==================== Statistics ====================

    def get_stats(self) -> dict:
        """Get statistics about loaded legacy data"""
        self.load_data()
        return {
            "client_car_mappings": len(self._client_cars_mapping),
            "clients_with_history": len(self._order_history),
            "total_historical_orders": sum(len(o) for o in self._order_history.values()),
            "order_details_count": len(self._order_details),
        }

    # ==================== Combined History ====================

    def format_legacy_order(self, order: dict, client_code: str = None) -> dict:
        """
        Format legacy order to match current order structure.

        Args:
            order: Raw legacy order data
            client_code: Optional client code to include

        Returns:
            Formatted order dict compatible with current system
        """
        # Get details if available
        order_number = order.get("number", "")
        details = self.get_order_details(order_number)

        formatted = {
            "ref": None,  # Legacy orders don't have Ref_Key in Rent1C
            "number": order_number,
            "date": order.get("date", ""),
            "sum": float(order.get("sum", 0) or 0),
            "status": "История",  # Mark as historical
            "car_name": order.get("car_name", ""),
            "is_legacy": True,
            "source": "185.222",
        }

        if client_code:
            formatted["client_code"] = client_code

        if details:
            formatted["works"] = details.get("works", [])
            formatted["goods"] = details.get("goods", [])

        return formatted


# Singleton instance
_legacy_service: Optional[LegacyDataService] = None


def get_legacy_service() -> LegacyDataService:
    """Get Legacy data service singleton"""
    global _legacy_service
    if _legacy_service is None:
        _legacy_service = LegacyDataService()
        _legacy_service.load_data()
    return _legacy_service
