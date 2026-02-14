#!/usr/bin/env python3
"""
Test suite for SQL Query Script

This script tests the functionality of the SQL query executor
and verifies that all planned queries execute correctly.
"""

import unittest
import tempfile
import os
import json
from sql_query_script import SQLQueryExecutor, QueryPlan


class TestSQLQueryExecutor(unittest.TestCase):
    """Test cases for SQLQueryExecutor class"""
    
    def setUp(self):
        """Set up test environment"""
        self.db_path = ":memory:"
        self.executor = SQLQueryExecutor(self.db_path)
        self.executor.connect()
        self.executor.create_schema()
        self.executor.insert_sample_data()
    
    def tearDown(self):
        """Clean up after tests"""
        self.executor.disconnect()
    
    def test_connection(self):
        """Test database connection"""
        self.assertIsNotNone(self.executor.connection)
        self.assertIsNotNone(self.executor.cursor)
    
    def test_schema_creation(self):
        """Test that tables are created correctly"""
        # Check if tables exist
        tables_query = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('users', 'products', 'orders')
        """
        self.executor.cursor.execute(tables_query)
        tables = [row[0] for row in self.executor.cursor.fetchall()]
        
        self.assertIn('users', tables)
        self.assertIn('products', tables)
        self.assertIn('orders', tables)
    
    def test_sample_data_insertion(self):
        """Test that sample data is inserted correctly"""
        # Check users
        self.executor.cursor.execute("SELECT COUNT(*) FROM users")
        user_count = self.executor.cursor.fetchone()[0]
        self.assertEqual(user_count, 4)
        
        # Check products
        self.executor.cursor.execute("SELECT COUNT(*) FROM products")
        product_count = self.executor.cursor.fetchone()[0]
        self.assertEqual(product_count, 5)
        
        # Check orders
        self.executor.cursor.execute("SELECT COUNT(*) FROM orders")
        order_count = self.executor.cursor.fetchone()[0]
        self.assertEqual(order_count, 6)
    
    def test_query_plan_creation(self):
        """Test query plan creation and management"""
        self.executor.create_query_plans()
        
        # Should have 6 query plans
        self.assertEqual(len(self.executor.query_plans), 6)
        
        # Check specific query plans exist
        plan_names = [plan.name for plan in self.executor.query_plans]
        expected_plans = [
            'count_users', 'list_users', 'user_order_summary',
            'top_products', 'category_revenue', 'recent_orders'
        ]
        
        for expected_plan in expected_plans:
            self.assertIn(expected_plan, plan_names)
    
    def test_single_query_execution(self):
        """Test execution of a single query plan"""
        plan = QueryPlan(
            name="test_count",
            sql="SELECT COUNT(*) FROM users",
            description="Test user count",
            expected_result_type="single"
        )
        
        result = self.executor.execute_query_plan(plan)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['plan_name'], 'test_count')
        self.assertGreater(result['execution_time'], 0)
        self.assertEqual(result['result'][0], 4)  # Should have 4 users
    
    def test_multiple_query_execution(self):
        """Test execution of multiple query plans"""
        self.executor.create_query_plans()
        self.executor.execute_all_plans()
        
        # Should have results for all plans
        self.assertEqual(len(self.executor.execution_results), 6)
        
        # All queries should succeed
        for result in self.executor.execution_results:
            self.assertTrue(result['success'])
    
    def test_error_handling(self):
        """Test error handling for invalid queries"""
        plan = QueryPlan(
            name="invalid_query",
            sql="SELECT * FROM non_existent_table",
            description="Invalid query test",
            expected_result_type="multiple"
        )
        
        result = self.executor.execute_query_plan(plan)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIsNone(result['result'])
    
    def test_result_export(self):
        """Test result export functionality"""
        # Create temporary file for export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = f.name
        
        try:
            # Execute queries and export results
            self.executor.create_query_plans()
            self.executor.execute_all_plans()
            self.executor.export_results(export_path)
            
            # Verify export file exists and contains valid JSON
            self.assertTrue(os.path.exists(export_path))
            
            with open(export_path, 'r') as f:
                export_data = json.load(f)
            
            # Check export structure
            self.assertIn('execution_timestamp', export_data)
            self.assertIn('database_path', export_data)
            self.assertIn('total_queries', export_data)
            self.assertIn('results', export_data)
            
            # Should have 6 results
            self.assertEqual(export_data['total_queries'], 6)
            self.assertEqual(len(export_data['results']), 6)
            
        finally:
            # Clean up temporary file
            if os.path.exists(export_path):
                os.unlink(export_path)


class TestQueryPlans(unittest.TestCase):
    """Test individual query plans"""
    
    def setUp(self):
        """Set up test environment"""
        self.db_path = ":memory:"
        self.executor = SQLQueryExecutor(self.db_path)
        self.executor.connect()
        self.executor.create_schema()
        self.executor.insert_sample_data()
        self.executor.create_query_plans()
    
    def tearDown(self):
        """Clean up after tests"""
        self.executor.disconnect()
    
    def test_count_users_query(self):
        """Test user count query"""
        plan = next(p for p in self.executor.query_plans if p.name == 'count_users')
        result = self.executor.execute_query_plan(plan)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['result'][0], 4)  # 4 users
    
    def test_user_order_summary_query(self):
        """Test user order summary query"""
        plan = next(p for p in self.executor.query_plans if p.name == 'user_order_summary')
        result = self.executor.execute_query_plan(plan)
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['result']), 4)  # 4 users
        
        # Check column structure
        expected_columns = ['user_name', 'order_count', 'total_spent']
        self.assertEqual(result['column_names'], expected_columns)
    
    def test_top_products_query(self):
        """Test top products query"""
        plan = next(p for p in self.executor.query_plans if p.name == 'top_products')
        result = self.executor.execute_query_plan(plan)
        
        self.assertTrue(result['success'])
        self.assertGreater(len(result['result']), 0)
        
        # Check column structure
        expected_columns = ['product_name', 'category', 'total_quantity', 'total_revenue']
        self.assertEqual(result['column_names'], expected_columns)


def run_tests():
    """Run all tests and display results"""
    print("Running SQL Query Script Tests")
    print("="*50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSQLQueryExecutor)
    suite.addTests(loader.loadTestsFromTestCase(TestQueryPlans))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n[SUCCESS] All tests passed!")
    else:
        print("\n[FAILURE] Some tests failed!")


if __name__ == "__main__":
    run_tests()