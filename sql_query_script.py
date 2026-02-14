#!/usr/bin/env python3
"""
SQL Query Script with Planning Phase

This script demonstrates a comprehensive SQL query execution workflow
with planning, execution, and result analysis phases.
"""

import sqlite3
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class QueryPlan:
    """Represents a planned SQL query with metadata"""
    name: str
    sql: str
    description: str
    expected_result_type: str  # 'single', 'multiple', 'none'
    parameters: Optional[Dict[str, Any]] = None
    

class SQLQueryExecutor:
    """Main class for executing SQL queries with planning"""
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self.query_plans: List[QueryPlan] = []
        self.execution_results: List[Dict[str, Any]] = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> None:
        """Establish database connection"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.cursor = self.connection.cursor()
            self.logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            self.logger.error(f"Database connection failed: {e}")
            raise
    
    def disconnect(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.logger.info("Database connection closed")
    
    def create_schema(self) -> None:
        """Create database tables"""
        schema_queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                category TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
            """
        ]
        
        for query in schema_queries:
            self.cursor.execute(query)
        self.connection.commit()
        self.logger.info("Database schema created successfully")
    
    def insert_sample_data(self) -> None:
        """Insert sample data for testing"""
        # Insert users
        users = [
            ("Alice Johnson", "alice@example.com"),
            ("Bob Smith", "bob@example.com"),
            ("Charlie Brown", "charlie@example.com"),
            ("Diana Prince", "diana@example.com")
        ]
        
        for name, email in users:
            self.cursor.execute(
                "INSERT OR IGNORE INTO users (name, email) VALUES (?, ?)",
                (name, email)
            )
        
        # Insert products
        products = [
            ("Laptop", 999.99, "Electronics"),
            ("Smartphone", 699.99, "Electronics"),
            ("Book", 29.99, "Education"),
            ("Coffee Mug", 12.99, "Home"),
            ("Headphones", 149.99, "Electronics")
        ]
        
        for name, price, category in products:
            self.cursor.execute(
                "INSERT OR IGNORE INTO products (name, price, category) VALUES (?, ?, ?)",
                (name, price, category)
            )
        
        # Insert orders
        orders = [
            (1, 1, 1),  # Alice buys Laptop
            (1, 3, 2),  # Alice buys 2 Books
            (2, 2, 1),  # Bob buys Smartphone
            (3, 4, 3),  # Charlie buys 3 Coffee Mugs
            (4, 5, 1),  # Diana buys Headphones
            (2, 1, 1),  # Bob buys Laptop
        ]
        
        for user_id, product_id, quantity in orders:
            self.cursor.execute(
                "INSERT INTO orders (user_id, product_id, quantity) VALUES (?, ?, ?)",
                (user_id, product_id, quantity)
            )
        
        self.connection.commit()
        self.logger.info("Sample data inserted successfully")
    
    def add_query_plan(self, plan: QueryPlan) -> None:
        """Add a query to the execution plan"""
        self.query_plans.append(plan)
        self.logger.info(f"Added query plan: {plan.name}")
    
    def create_query_plans(self) -> None:
        """Define all SQL queries to be executed"""
        plans = [
            QueryPlan(
                name="count_users",
                sql="SELECT COUNT(*) as user_count FROM users",
                description="Count total number of users",
                expected_result_type="single"
            ),
            QueryPlan(
                name="list_users",
                sql="SELECT id, name, email, created_at FROM users ORDER BY name",
                description="List all users sorted by name",
                expected_result_type="multiple"
            ),
            QueryPlan(
                name="user_order_summary",
                sql="""
                SELECT 
                    u.name as user_name,
                    COUNT(o.id) as order_count,
                    SUM(o.quantity * p.price) as total_spent
                FROM users u
                LEFT JOIN orders o ON u.id = o.user_id
                LEFT JOIN products p ON o.product_id = p.id
                GROUP BY u.id, u.name
                ORDER BY total_spent DESC
                """,
                description="User order summary with total spending",
                expected_result_type="multiple"
            ),
            QueryPlan(
                name="top_products",
                sql="""
                SELECT 
                    p.name as product_name,
                    p.category,
                    SUM(o.quantity) as total_quantity,
                    SUM(o.quantity * p.price) as total_revenue
                FROM products p
                JOIN orders o ON p.id = o.product_id
                GROUP BY p.id, p.name, p.category
                ORDER BY total_revenue DESC
                """,
                description="Top products by revenue",
                expected_result_type="multiple"
            ),
            QueryPlan(
                name="category_revenue",
                sql="""
                SELECT 
                    category,
                    COUNT(DISTINCT p.id) as product_count,
                    SUM(o.quantity * p.price) as total_revenue
                FROM products p
                JOIN orders o ON p.id = o.product_id
                GROUP BY category
                ORDER BY total_revenue DESC
                """,
                description="Revenue by product category",
                expected_result_type="multiple"
            ),
            QueryPlan(
                name="recent_orders",
                sql="""
                SELECT 
                    u.name as user_name,
                    p.name as product_name,
                    o.quantity,
                    o.order_date
                FROM orders o
                JOIN users u ON o.user_id = u.id
                JOIN products p ON o.product_id = p.id
                ORDER BY o.order_date DESC
                LIMIT 5
                """,
                description="Most recent orders",
                expected_result_type="multiple"
            )
        ]
        
        for plan in plans:
            self.add_query_plan(plan)
    
    def execute_query_plan(self, plan: QueryPlan) -> Dict[str, Any]:
        """Execute a single query plan and return results"""
        start_time = time.time()
        
        try:
            if plan.parameters:
                self.cursor.execute(plan.sql, plan.parameters)
            else:
                self.cursor.execute(plan.sql)
            
            execution_time = time.time() - start_time
            
            if plan.expected_result_type == "single":
                result = self.cursor.fetchone()
            elif plan.expected_result_type == "multiple":
                result = self.cursor.fetchall()
            else:
                result = None
            
            # Get column names
            column_names = [description[0] for description in self.cursor.description] if self.cursor.description else []
            
            return {
                "plan_name": plan.name,
                "success": True,
                "execution_time": execution_time,
                "result": result,
                "column_names": column_names,
                "row_count": len(result) if result else 0
            }
            
        except sqlite3.Error as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Query execution failed: {plan.name} - {e}")
            return {
                "plan_name": plan.name,
                "success": False,
                "execution_time": execution_time,
                "error": str(e),
                "result": None,
                "column_names": [],
                "row_count": 0
            }
    
    def execute_all_plans(self) -> None:
        """Execute all query plans in sequence"""
        self.logger.info(f"Starting execution of {len(self.query_plans)} query plans")
        
        for plan in self.query_plans:
            self.logger.info(f"Executing: {plan.name}")
            result = self.execute_query_plan(plan)
            self.execution_results.append(result)
    
    def display_results(self) -> None:
        """Display execution results in a formatted way"""
        print("\n" + "="*60)
        print("SQL QUERY EXECUTION RESULTS")
        print("="*60)
        
        for result in self.execution_results:
            print(f"\nQuery: {result['plan_name']}")
            print(f"Status: {'SUCCESS' if result['success'] else 'FAILED'}")
            print(f"Execution Time: {result['execution_time']:.4f} seconds")
            
            if result['success']:
                if result['row_count'] > 0:
                    print(f"Rows Returned: {result['row_count']}")
                    
                    # Display column headers
                    if result['column_names']:
                        print("\n" + " | ".join(result['column_names']))
                        print("-" * (len(" | ".join(result['column_names'])) + 10))
                    
                    # Display data
                    if isinstance(result['result'], list):
                        for row in result['result']:
                            formatted_row = [str(item) if item is not None else "NULL" for item in row]
                            print(" | ".join(formatted_row))
                    else:
                        # Single result (tuple)
                        formatted_row = [str(item) if item is not None else "NULL" for item in result['result']]
                        print(" | ".join(formatted_row))
                else:
                    print("No rows returned")
            else:
                print(f"Error: {result['error']}")
    
    def export_results(self, filename: str = "query_results.json") -> None:
        """Export execution results to JSON file"""
        export_data = {
            "execution_timestamp": datetime.now().isoformat(),
            "database_path": self.db_path,
            "total_queries": len(self.execution_results),
            "successful_queries": sum(1 for r in self.execution_results if r['success']),
            "failed_queries": sum(1 for r in self.execution_results if not r['success']),
            "results": self.execution_results
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        self.logger.info(f"Results exported to {filename}")
    
    def run_complete_workflow(self) -> None:
        """Execute the complete SQL query workflow"""
        try:
            # Phase 1: Setup
            self.logger.info("=== PHASE 1: SETUP ===")
            self.connect()
            self.create_schema()
            self.insert_sample_data()
            
            # Phase 2: Planning
            self.logger.info("=== PHASE 2: PLANNING ===")
            self.create_query_plans()
            
            # Phase 3: Execution
            self.logger.info("=== PHASE 3: EXECUTION ===")
            self.execute_all_plans()
            
            # Phase 4: Results
            self.logger.info("=== PHASE 4: RESULTS ===")
            self.display_results()
            self.export_results()
            
            # Phase 5: Cleanup
            self.logger.info("=== PHASE 5: CLEANUP ===")
            self.disconnect()
            
            self.logger.info("SQL query workflow completed successfully")
            
        except Exception as e:
            self.logger.error(f"Workflow failed: {e}")
            if self.connection:
                self.disconnect()


def main():
    """Main function to run the SQL query script"""
    print("SQL Query Script with Planning Phase")
    print("="*50)
    
    # Create executor with in-memory database
    executor = SQLQueryExecutor(":memory:")
    
    # Run complete workflow
    executor.run_complete_workflow()
    
    print("\nScript execution completed!")


if __name__ == "__main__":
    main()