#!/usr/bin/env python3
"""
Comprehensive VectorLiteDB Test Suite Runner

This script runs all the tests and experiments to thoroughly understand
VectorLiteDB's capabilities, limits, and behavior patterns.

Usage:
    python run_comprehensive_tests.py [--quick] [--experiments-only] [--tests-only]
    
Options:
    --quick: Run only essential tests (skip time-consuming experiments)
    --experiments-only: Run only performance experiments
    --tests-only: Run only correctness tests
"""

import sys
import os
import time
import argparse
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ SUCCESS ({duration:.1f}s)")
            if result.stdout:
                print("Output:")
                print(result.stdout)
        else:
            print(f"❌ FAILED ({duration:.1f}s)")
            print("Error output:")
            print(result.stderr)
            if result.stdout:
                print("Standard output:")
                print(result.stdout)
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"⏰ TIMEOUT (300s)")
        return False
    except Exception as e:
        print(f"💥 EXCEPTION: {e}")
        return False

def run_pytest_tests():
    """Run all pytest-based tests"""
    print("\n🧪 Running Correctness Tests")
    
    tests = [
        ("pytest tests/test_smoke.py -v", "Basic CRUD and search tests"),
        ("pytest tests/test_metrics.py -v", "Distance metric tests"),
        ("pytest tests/test_accuracy_parity.py -v", "Accuracy parity vs NumPy"),
        ("pytest tests/test_persistence_crash.py -v", "Persistence and crash tests"),
        ("pytest tests/test_metadata_filters.py -v", "Metadata filtering tests"),
    ]
    
    results = []
    for cmd, desc in tests:
        success = run_command(cmd, desc)
        results.append((desc, success))
    
    return results

def run_experiments():
    """Run performance and behavior experiments"""
    print("\n🔬 Running Performance Experiments")
    
    experiments = [
        ("python experiments/latency_sweep.py", "Performance and latency sweep"),
        ("python experiments/concurrency_probe.py", "Concurrency behavior probe"),
        ("python experiments/big_metadata.py", "Big metadata pressure tests"),
    ]
    
    results = []
    for cmd, desc in experiments:
        success = run_command(cmd, desc)
        results.append((desc, success))
    
    return results

def run_quick_tests():
    """Run only essential tests for quick validation"""
    print("\n⚡ Running Quick Validation Tests")
    
    quick_tests = [
        ("pytest tests/test_smoke.py -v", "Basic functionality"),
        ("pytest tests/test_accuracy_parity.py::test_parity_small_random -v", "Accuracy check"),
        ("python -c \"from vectorlitedb import VectorLiteDB; import tempfile; db = VectorLiteDB(tempfile.mktemp(), dimension=4); db.insert('test', [1,0,0,0], {}); print('✅ VectorLiteDB import and basic usage works')\"", "Import and basic usage"),
    ]
    
    results = []
    for cmd, desc in quick_tests:
        success = run_command(cmd, desc)
        results.append((desc, success))
    
    return results

def check_dependencies():
    """Check if all required dependencies are available"""
    print("\n📦 Checking Dependencies")
    
    required_packages = [
        "vectorlitedb",
        "numpy", 
        "pytest",
        "psutil"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (missing)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        return False
    
    return True

def generate_report(test_results, experiment_results):
    """Generate a summary report"""
    print("\n" + "="*80)
    print("📊 COMPREHENSIVE TEST REPORT")
    print("="*80)
    
    # Test results
    print("\n🧪 CORRECTNESS TESTS:")
    test_success = 0
    for desc, success in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {desc}")
        if success:
            test_success += 1
    
    # Experiment results
    print("\n🔬 EXPERIMENTS:")
    exp_success = 0
    for desc, success in experiment_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {desc}")
        if success:
            exp_success += 1
    
    # Summary
    total_tests = len(test_results) + len(experiment_results)
    total_success = test_success + exp_success
    
    print(f"\n📈 SUMMARY:")
    print(f"  Tests: {test_success}/{len(test_results)} passed")
    print(f"  Experiments: {exp_success}/{len(experiment_results)} passed")
    print(f"  Overall: {total_success}/{total_tests} passed ({100*total_success/total_tests:.1f}%)")
    
    if total_success == total_tests:
        print("\n🎉 ALL TESTS PASSED! VectorLiteDB is working correctly.")
    else:
        print(f"\n⚠️  {total_tests - total_success} tests failed. Check the output above for details.")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    if test_success == len(test_results):
        print("  ✅ VectorLiteDB correctness is verified")
    else:
        print("  ❌ Some correctness tests failed - investigate before production use")
    
    if exp_success == len(experiment_results):
        print("  ✅ All experiments completed successfully")
        print("  📊 Check generated CSV files and output for performance insights")
    else:
        print("  ⚠️  Some experiments failed - may indicate resource limits or issues")
    
    print("\n📁 Generated files:")
    files_to_check = [
        "latency_sweep.csv",
        "bench_*.db",  # These should be cleaned up
        "conc.db",
        "bigmeta.db"
    ]
    
    for pattern in files_to_check:
        if "*" in pattern:
            import glob
            matches = glob.glob(pattern)
            if matches:
                print(f"  {pattern}: {len(matches)} files found")
        else:
            if os.path.exists(pattern):
                size = os.path.getsize(pattern)
                print(f"  {pattern}: {size/1024:.1f} KB")

def cleanup_temp_files():
    """Clean up temporary files created during testing"""
    print("\n🧹 Cleaning up temporary files...")
    
    temp_patterns = [
        "bench_*.db",
        "conc.db", 
        "bigmeta.db",
        "metric_bench_*.db",
        "dim_bench_*.db",
        "topk_bench.db",
        "*.db"  # Be careful with this one
    ]
    
    import glob
    cleaned = 0
    for pattern in temp_patterns:
        matches = glob.glob(pattern)
        for match in matches:
            try:
                # Only remove files that look like test files
                if any(keyword in match for keyword in ["bench", "conc", "bigmeta", "metric", "dim", "topk"]):
                    os.remove(match)
                    cleaned += 1
            except Exception as e:
                print(f"  Could not remove {match}: {e}")
    
    if cleaned > 0:
        print(f"  Removed {cleaned} temporary files")
    else:
        print("  No temporary files to clean up")

def main():
    parser = argparse.ArgumentParser(description="Run comprehensive VectorLiteDB tests")
    parser.add_argument("--quick", action="store_true", help="Run only essential tests")
    parser.add_argument("--experiments-only", action="store_true", help="Run only experiments")
    parser.add_argument("--tests-only", action="store_true", help="Run only correctness tests")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't clean up temporary files")
    
    args = parser.parse_args()
    
    print("🚀 VectorLiteDB Comprehensive Test Suite")
    print("="*60)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Missing dependencies. Please install them and try again.")
        sys.exit(1)
    
    # Run tests based on arguments
    test_results = []
    experiment_results = []
    
    if args.quick:
        test_results = run_quick_tests()
    elif args.experiments_only:
        experiment_results = run_experiments()
    elif args.tests_only:
        test_results = run_pytest_tests()
    else:
        # Run everything
        test_results = run_pytest_tests()
        experiment_results = run_experiments()
    
    # Generate report
    generate_report(test_results, experiment_results)
    
    # Cleanup
    if not args.no_cleanup:
        cleanup_temp_files()
    
    # Exit with appropriate code
    total_failed = sum(1 for _, success in test_results + experiment_results if not success)
    if total_failed > 0:
        print(f"\n❌ {total_failed} tests failed")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()



