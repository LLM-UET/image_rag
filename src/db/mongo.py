"""
MongoDB Handler - Database connector for telecom package storage.

This module provides:
- MongoHandler: Class for MongoDB operations
- Upsert functionality with compound key (name + partner_name)
- CRUD operations for telecom packages
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from pymongo import MongoClient, UpdateOne
    from pymongo.errors import ConnectionFailure, OperationFailure
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "telecom_db")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "packages")


class MongoHandler:
    """
    MongoDB handler for telecom package storage.
    
    Provides upsert functionality with compound unique index on 
    (name, partner_name, billing_cycle) to prevent duplicates.
    """
    
    def __init__(
        self, 
        uri: Optional[str] = None,
        database: Optional[str] = None,
        collection: Optional[str] = None
    ):
        """
        Initialize MongoDB connection.
        
        Args:
            uri: MongoDB connection URI (default from env)
            database: Database name (default from env)
            collection: Collection name (default from env)
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError(
                "pymongo is not installed. Install it with: pip install pymongo"
            )
        
        self.uri = uri or MONGO_URI
        self.database_name = database or MONGO_DATABASE
        self.collection_name = collection or MONGO_COLLECTION
        
        self._client: Optional[MongoClient] = None
        self._db = None
        self._collection = None
        
        logger.info(f"MongoHandler initialized for {self.database_name}.{self.collection_name}")
    
    def connect(self) -> bool:
        """
        Establish connection to MongoDB.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            # Verify connection
            self._client.admin.command('ping')
            
            self._db = self._client[self.database_name]
            self._collection = self._db[self.collection_name]
            
            # Create compound index for upsert operations
            self._ensure_indexes()
            
            logger.info(f"Connected to MongoDB: {self.uri}")
            return True
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"MongoDB error: {e}")
            return False
    
    def _ensure_indexes(self):
        """Create necessary indexes for efficient operations."""
        try:
            # Compound unique index for deduplication
            self._collection.create_index(
                [
                    ("name", 1),
                    ("partner_name", 1),
                    ("attributes.billing_cycle", 1)
                ],
                unique=True,
                name="package_unique_idx",
                background=True
            )
            
            # Index for partner queries
            self._collection.create_index(
                [("partner_name", 1)],
                name="partner_idx",
                background=True
            )
            
            # Index for service type queries
            self._collection.create_index(
                [("service_type", 1)],
                name="service_type_idx",
                background=True
            )
            
            logger.info("MongoDB indexes ensured")
            
        except Exception as e:
            logger.warning(f"Failed to create indexes: {e}")
    
    def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("MongoDB connection closed")
    
    def upsert_packages(self, packages: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Upsert multiple packages into MongoDB.
        
        Uses compound key (name + partner_name + billing_cycle) 
        for uniqueness. Updates existing records, inserts new ones.
        
        Args:
            packages: List of package dictionaries
            
        Returns:
            Dictionary with counts: {"inserted": N, "updated": M, "errors": E}
        """
        if not self._collection:
            if not self.connect():
                raise ConnectionError("Failed to connect to MongoDB")
        
        if not packages:
            return {"inserted": 0, "updated": 0, "errors": 0}
        
        results = {"inserted": 0, "updated": 0, "errors": 0}
        operations = []
        
        for pkg in packages:
            try:
                # Build filter for upsert
                filter_doc = {
                    "name": pkg.get("name") or pkg.get("package_name"),
                    "partner_name": pkg.get("partner_name"),
                }
                
                # Include billing_cycle in filter if present
                billing_cycle = pkg.get("attributes", {}).get("billing_cycle")
                if billing_cycle:
                    filter_doc["attributes.billing_cycle"] = billing_cycle
                
                # Prepare update document
                update_doc = {
                    "$set": {
                        **pkg,
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow()
                    }
                }
                
                operations.append(
                    UpdateOne(filter_doc, update_doc, upsert=True)
                )
                
            except Exception as e:
                logger.error(f"Error preparing package for upsert: {e}")
                results["errors"] += 1
        
        if not operations:
            return results
        
        try:
            # Execute bulk write
            result = self._collection.bulk_write(operations, ordered=False)
            
            results["inserted"] = result.upserted_count
            results["updated"] = result.modified_count
            
            logger.info(
                f"Upsert complete: {results['inserted']} inserted, "
                f"{results['updated']} updated, {results['errors']} errors"
            )
            
        except OperationFailure as e:
            logger.error(f"Bulk write failed: {e}")
            results["errors"] += len(operations)
        except Exception as e:
            logger.error(f"Unexpected error during upsert: {e}")
            results["errors"] += len(operations)
        
        return results
    
    def find_packages(
        self, 
        filter_doc: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Find packages matching filter.
        
        Args:
            filter_doc: MongoDB filter document (empty for all)
            limit: Maximum number of results
            
        Returns:
            List of package documents
        """
        if not self._collection:
            if not self.connect():
                return []
        
        try:
            cursor = self._collection.find(
                filter_doc or {},
                {"_id": 0}  # Exclude MongoDB _id
            ).limit(limit)
            
            return list(cursor)
            
        except Exception as e:
            logger.error(f"Find failed: {e}")
            return []
    
    def find_by_partner(self, partner_name: str) -> List[Dict[str, Any]]:
        """
        Find all packages for a specific partner.
        
        Args:
            partner_name: Partner/provider name
            
        Returns:
            List of packages
        """
        return self.find_packages({"partner_name": partner_name}, limit=1000)
    
    def find_by_service_type(self, service_type: str) -> List[Dict[str, Any]]:
        """
        Find all packages of a specific service type.
        
        Args:
            service_type: Service type (e.g., "Television", "Internet")
            
        Returns:
            List of packages
        """
        return self.find_packages({"service_type": service_type}, limit=1000)
    
    def count_packages(self, filter_doc: Optional[Dict[str, Any]] = None) -> int:
        """
        Count packages matching filter.
        
        Args:
            filter_doc: MongoDB filter document
            
        Returns:
            Count of matching documents
        """
        if not self._collection:
            if not self.connect():
                return 0
        
        try:
            return self._collection.count_documents(filter_doc or {})
        except Exception as e:
            logger.error(f"Count failed: {e}")
            return 0
    
    def delete_packages(
        self, 
        filter_doc: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Delete packages matching filter.
        
        Args:
            filter_doc: MongoDB filter document (REQUIRED for safety)
            
        Returns:
            Number of deleted documents
        """
        if not filter_doc:
            raise ValueError("Filter document required for delete operation")
        
        if not self._collection:
            if not self.connect():
                return 0
        
        try:
            result = self._collection.delete_many(filter_doc)
            logger.info(f"Deleted {result.deleted_count} documents")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dictionary with collection stats
        """
        if not self._collection:
            if not self.connect():
                return {}
        
        try:
            stats = {
                "total_packages": self.count_packages(),
                "by_partner": {},
                "by_service_type": {}
            }
            
            # Count by partner
            pipeline = [
                {"$group": {"_id": "$partner_name", "count": {"$sum": 1}}}
            ]
            for doc in self._collection.aggregate(pipeline):
                stats["by_partner"][doc["_id"]] = doc["count"]
            
            # Count by service type
            pipeline = [
                {"$group": {"_id": "$service_type", "count": {"$sum": 1}}}
            ]
            for doc in self._collection.aggregate(pipeline):
                stats["by_service_type"][doc["_id"]] = doc["count"]
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function
def upsert_packages_to_mongo(
    packages: List[Dict[str, Any]],
    uri: Optional[str] = None,
    database: Optional[str] = None,
    collection: Optional[str] = None
) -> Dict[str, int]:
    """
    Convenience function to upsert packages to MongoDB.
    
    Args:
        packages: List of package dictionaries
        uri: MongoDB URI
        database: Database name
        collection: Collection name
        
    Returns:
        Results dictionary
    """
    with MongoHandler(uri, database, collection) as handler:
        return handler.upsert_packages(packages)


if __name__ == "__main__":
    # Test MongoDB handler
    import json
    
    # Sample packages for testing
    test_packages = [
        {
            "name": "VIP",
            "partner_name": "TV360",
            "service_type": "Television",
            "attributes": {
                "price": 80000,
                "billing_cycle": "1 tháng",
                "payment_type": "prepaid"
            }
        },
        {
            "name": "STANDARD",
            "partner_name": "TV360",
            "service_type": "Television",
            "attributes": {
                "price": 50000,
                "billing_cycle": "1 tháng",
                "payment_type": "prepaid"
            }
        }
    ]
    
    print("Testing MongoHandler...")
    print(f"MongoDB URI: {MONGO_URI}")
    print(f"Database: {MONGO_DATABASE}")
    print(f"Collection: {MONGO_COLLECTION}")
    
    try:
        with MongoHandler() as handler:
            # Test upsert
            results = handler.upsert_packages(test_packages)
            print(f"\nUpsert results: {json.dumps(results)}")
            
            # Test find
            packages = handler.find_by_partner("TV360")
            print(f"\nPackages found: {len(packages)}")
            
            # Test statistics
            stats = handler.get_statistics()
            print(f"\nStatistics: {json.dumps(stats, indent=2)}")
            
    except Exception as e:
        print(f"\nTest failed: {e}")
        print("Make sure MongoDB is running and accessible")
