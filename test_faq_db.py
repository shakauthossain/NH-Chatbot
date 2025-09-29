#!/usr/bin/env python3

# Test script to verify FAQ database is loading and searching correctly
import os
import sys
sys.path.append('.')

from faq_services import load_faqs, db

def test_faq_database():
    print("Testing FAQ Database Loading and Search...")
    
    # Test 1: Check if database loads
    try:
        test_db = load_faqs()
        print("✅ Database loading: SUCCESS")
    except Exception as e:
        print(f"❌ Database loading: FAILED - {e}")
        return
    
    # Test 2: Check if we have documents
    try:
        # Try a search to see if there are documents
        results = test_db.similarity_search("services", k=2)
        print(f"✅ Documents loaded: {len(results)} documents found")
        
        if results:
            print("\nSample search result:")
            print(f"Content: {results[0].page_content[:200]}...")
        else:
            print("❌ No documents found in database")
            
    except Exception as e:
        print(f"❌ Database search: FAILED - {e}")
        return
    
    # Test 3: Test specific queries
    test_queries = [
        "What services does Notionhive offer?",
        "How much does it cost?",
        "What is web development?"
    ]
    
    print("\n" + "="*50)
    print("TESTING SPECIFIC QUERIES:")
    print("="*50)
    
    for query in test_queries:
        try:
            results = test_db.similarity_search(query, k=1)
            if results:
                print(f"\nQuery: {query}")
                print(f"Best match: {results[0].page_content[:150]}...")
            else:
                print(f"\nQuery: {query}")
                print("No matches found")
        except Exception as e:
            print(f"\nQuery: {query}")
            print(f"Error: {e}")

if __name__ == "__main__":
    test_faq_database()