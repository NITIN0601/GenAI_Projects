#!/usr/bin/env python3
"""
Test the complete query engine with real queries.
"""

import sys
sys.path.insert(0, '.')

from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
from rag.query_processor import get_query_processor

console = Console()


def test_query(query: str):
    """Test a single query."""
    console.print(f"\n[bold cyan]Query:[/bold cyan] {query}")
    console.print("─" * 70)
    
    try:
        processor = get_query_processor()
        result = processor.process_query(query)
        
        console.print(f"[green]Query Type:[/green] {result.get('query_type')}")
        
        # Display results based on type
        if "table" in result:
            # Show as table
            table_data = result["table"]
            if table_data:
                rich_table = RichTable(show_header=True, show_lines=True)
                
                # Add columns
                for key in table_data[0].keys():
                    rich_table.add_column(str(key), style="cyan")
                
                # Add rows
                for row in table_data[:10]:  # Limit to 10 rows
                    rich_table.add_row(*[str(v) for v in row.values()])
                
                console.print(rich_table)
                
                if len(table_data) > 10:
                    console.print(f"[dim]... and {len(table_data) - 10} more rows[/dim]")
        
        elif "values" in result:
            # Show specific values
            for value in result["values"]:
                console.print(f"  • {value.get('metric')}: {value.get('value')} ({value.get('period')})")
        
        elif "aggregations" in result:
            # Show aggregations
            agg = result["aggregations"]
            console.print(f"  Count: {agg.get('count')}")
            console.print(f"  Sum: ${agg.get('sum', 0):,.0f}")
            console.print(f"  Average: ${agg.get('average', 0):,.0f}")
            console.print(f"  Min: ${agg.get('min', 0):,.0f}")
            console.print(f"  Max: ${agg.get('max', 0):,.0f}")
        
        console.print()
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


def main():
    """Test various query types."""
    console.print("\n[bold]Testing Query Engine[/bold]\n")
    console.print("=" * 70)
    
    # Test queries for each type
    test_queries = [
        # Type 1: Specific Value
        "What was net revenue in Q1 2025?",
        
        # Type 2: Comparison
        "Compare net revenues between Q1 2025 and Q1 2024",
        
        # Type 3: Trend
        "Show revenue trend for last 4 quarters",
        
        # Type 4: Aggregation
        "What was average revenue across all quarters?",
        
        # Type 5: Multi-Document
        "Show net revenues from all documents",
        
        # Type 6: Cross-Table (if we have multiple table types)
        # "Show revenue from income statement and total assets from balance sheet",
        
        # Type 7: Hierarchical
        "Show all revenue line items and their sub-items",
        
        # Special: Contractual Principal
        "Show difference between contractual principal and fair value",
    ]
    
    for query in test_queries:
        test_query(query)
        console.print()
    
    console.print("=" * 70)
    console.print("[bold green]Testing Complete![/bold green]\n")


if __name__ == "__main__":
    main()
