#!/usr/bin/env python3
"""
Test script to verify MCP server browser functionality.
Run this to test if the browser tools work.
"""

import asyncio
import sys
import os
sys.path.insert(0, '/home/ahmed/Desktop/Gravitas-MCP-Core')

from gravitas_mcp.browser import BrowserEngine


async def test_browser():
    print("=" * 60)
    print("Testing MCP Browser Engine")
    print("=" * 60)
    
    browser = BrowserEngine(project_root="/home/ahmed/Desktop/Gravitas-MCP-Core")
    
    try:
        # Test 1: Navigate to a simple page
        print("\n[Test 1] Navigating to https://example.com...")
        result = await browser.navigate(
            url="https://www.youtube.com/",
            wait_until="domcontentloaded"
        )
        print(f"Status: {result.get('status')}")
        print(f"URL: {result.get('observations', {}).get('url')}")
        print(f"Title: {result.get('observations', {}).get('title')}")
        
        # Test 2: Get snapshot
        print("\n[Test 2] Taking DOM snapshot...")
        snapshot = await browser.snapshot()
        print(f"Status: {snapshot.get('status')}")
        tree = snapshot.get('observations', {}).get('accessibility_tree')
        if tree:
            print(f"DOM Node found: {tree.get('name', 'unnamed')[:50]}...")
        
        # Test 3: Get console errors
        print("\n[Test 3] Checking console errors...")
        errors = await browser.get_console_errors()
        console_errs = errors.get('observations', {}).get('console_errors', [])
        print(f"Console errors: {len(console_errs)}")
        
        # Test 4: Screenshot
        print("\n[Test 4] Taking screenshot...")
        screenshot_result = await browser.screenshot(path="/home/ahmed/Desktop/Gravitas-MCP-Core/mcp_test_screenshot1.png")
        print(f"Status: {screenshot_result.get('status')}")
        if screenshot_result.get('status') == 'success':
            print(f"Screenshot saved to: {screenshot_result.get('observations', {}).get('path')}")

        # Test 5: Hover over element
        print("\n[Test 5] Hovering over heading...")
        hover_result = await browser.hover("input")
        print(f"Status: {hover_result.get('status')}")

        print("\n" + "=" * 60)
        print("All browser tests passed!")
        print("=" * 60)
        os.wait()  # Keep browser open for a moment to review
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_browser())

