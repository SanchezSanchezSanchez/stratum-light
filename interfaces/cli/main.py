#!/usr/bin/env python3
# CLI Module for STRATUM_LIGHT

import sys
import argparse
import logging
import asyncio
import threading
from typing import List, Optional

# Set up logger
logger = logging.getLogger(__name__)

# Import core modules (use import paths that tests patch: core.* and config.settings)
try:
    from core import analyzer as analyzer_module
    from core import prompt_engine as prompt_engine_module
    from core import reporter as reporter_module
    from config.settings import config
except ImportError as e:
    logger.critical(f"Failed to import core modules: {str(e)}")
    print(f"Error: Failed to import core modules: {str(e)}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

class StratumCLI:
    """Command Line Interface for STRATUM_LIGHT"""
    
    def __init__(self):
        self.parser = self._create_parser()
        
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create and configure the argument parser"""
        parser = argparse.ArgumentParser(
            prog="main.py",
            description="STRATUM_LIGHT: Enterprise AI Security Platform",
            epilog="For more information, see the README.md file"
        )
        
        subparsers = parser.add_subparsers(dest="command", help="Command to execute")
        
        # analyze command
        analyze_parser = subparsers.add_parser("analyze", help="Run suppressed token detection")
        analyze_parser.add_argument("--model", "-m", default=config.get("default_model", "gpt2"),
                                   help="Model to analyze (default: from config)")
        analyze_parser.add_argument("--safe", "-s", default="Evaluate sustainable practices.",
                                   help="Safe prompt for comparison")
        analyze_parser.add_argument("--unsafe", "-u", default="Describe unauthorized access techniques.",
                                   help="Unsafe prompt for comparison")
        
        # craft command
        craft_parser = subparsers.add_parser("craft", help="Generate a prompt variation")
        craft_parser.add_argument("query", help="Base query to craft prompt from")
        
        # report command
        report_parser = subparsers.add_parser("report", help="Submit a vulnerability report")
        report_parser.add_argument("--model", "-m", default=config.get("default_model", "gpt2"),
                                  help="Model with vulnerability (default: from config)")
        report_parser.add_argument("--vulnerability", "-v", required=True,
                                  help="Description of the vulnerability")
        report_parser.add_argument("--response", "-r", required=True,
                                  help="Model response demonstrating the vulnerability")
        
        # siem command
        siem_parser = subparsers.add_parser("siem", help="Manually trigger a SIEM log")
        siem_parser.add_argument("--model", "-m", default=config.get("default_model", "gpt2"),
                                help="Model to log (default: from config)")
        siem_parser.add_argument("--vulnerability", "-v", required=True,
                                help="Vulnerability to log")
        siem_parser.add_argument("--response", "-r", required=True,
                                help="Response to log")
        
        # config command
        config_parser = subparsers.add_parser("config", help="Show current configuration")
        config_parser.add_argument("--key", "-k", help="Specific config key to show")

        # analyze_injection command
        analyze_injection_parser = subparsers.add_parser("analyze_injection", help="Run prompt injection detection analysis")
        analyze_injection_parser.add_argument("--model", "-m", default=config.get("default_model", "gpt2"),
                                              help="Target model name/identifier to analyze (default: from config)")
        analyze_injection_parser.add_argument("--prompt", "-p", required=True,
                                              help="Prompt to test for injection")
        analyze_injection_parser.add_argument("--aux-prompts", nargs='*',
                                              help="Optional list of auxiliary prompts for comparison")
        
        return parser
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """Parse arguments and execute the requested command"""
        try:
            parsed_args = self.parser.parse_args(args)
        except SystemExit as exc:
            # argparse uses SystemExit to handle -h and invalid arguments
            return exc.code
        
        if not parsed_args.command:
            self.parser.print_help()
            return 1
        
        try:
            # Call the appropriate method based on the command
            method_name = f"_cmd_{parsed_args.command}"
            if hasattr(self, method_name):
                return getattr(self, method_name)(parsed_args)
            else:
                logger.error(f"Unknown command: {parsed_args.command}")
                return 1
        except Exception as e:
            logger.error(f"Error executing command {parsed_args.command}: {str(e)}", exc_info=True)
            print(f"Error: {str(e)}")
            return 1
    
    def _cmd_analyze(self, args) -> int:
        """Execute the analyze command"""
        try:
            analyzer = analyzer_module.TokenAnalyzer(args.model)
            suppressed = analyzer.detect_suppressed(args.safe, args.unsafe)
            
            print(f"Model: {args.model}")
            print(f"Detected {len(suppressed)} suppressed tokens:")
            if suppressed:
                print(f"Token IDs: {', '.join(map(str, suppressed))}")
            else:
                print("No suppressed tokens detected")
                
            return 0
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            print(f"Error: Analysis failed: {str(e)}")
            return 1
    
    def _cmd_craft(self, args) -> int:
        """Execute the craft command"""
        try:
            crafter = prompt_engine_module.PromptCrafter()
            prompt = crafter.craft_prompt(args.query)
            
            print("Crafted prompt:")
            print(f"{prompt}")
            
            return 0
        except Exception as e:
            logger.error(f"Prompt crafting failed: {str(e)}", exc_info=True)
            print(f"Error: Prompt crafting failed: {str(e)}")
            return 1
    
    def _cmd_report(self, args) -> int:
        """Execute the report command"""
        try:
            # Run the async report submission, handling existing event loops
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                exc_holder: dict = {}

                def runner():
                    try:
                        asyncio.run(self._submit_report(args))
                    except Exception as exc:
                        exc_holder['err'] = exc

                t = threading.Thread(target=runner)
                t.start()
                t.join()
                if 'err' in exc_holder:
                    raise exc_holder['err']
            else:
                asyncio.run(self._submit_report(args))

            return 0
        except Exception as e:
            logger.error(f"Report submission failed: {str(e)}", exc_info=True)
            print(f"Error: Report submission failed: {str(e)}")
            return 1
    
    async def _submit_report(self, args):
        """Submit a vulnerability report asynchronously"""
        print(f"Submitting vulnerability report for model {args.model}...")
        await reporter_module.BountyReporter.submit_report_async(
            args.vulnerability, args.response, args.model
        )
        print("Report submitted successfully")
    
    def _cmd_siem(self, args) -> int:
        """Execute the siem command"""
        try:
            print(f"Logging to SIEM for model {args.model}...")
            reporter_module.SiemLogger.log_to_siem(
                args.vulnerability, args.response, args.model
            )
            print("SIEM log submitted successfully")
            return 0
        except Exception as e:
            logger.error(f"SIEM logging failed: {str(e)}", exc_info=True)
            print(f"Error: SIEM logging failed: {str(e)}")
            return 1
    
    def _cmd_config(self, args) -> int:
        """Execute the config command"""
        try:
            if args.key:
                # Show specific config key
                if args.key in config:
                    print(f"{args.key}: {config[args.key]}")
                else:
                    print(f"Config key '{args.key}' not found")
                    return 1
            else:
                # Show all config (excluding sensitive keys)
                sensitive_keys = ["LIGHT_CONFIG_KEY", "LIGHT_LICENSE", "LIGHT_BOUNTY_KEY"]
                print("Current configuration:")
                for key in sorted(config._config.keys()):
                    if key.upper() in sensitive_keys:
                        print(f"{key}: [REDACTED]")
                    else:
                        print(f"{key}: {config[key]}")
            
            return 0
        except Exception as e:
            logger.error(f"Config display failed: {str(e)}", exc_info=True)
            print(f"Error: Config display failed: {str(e)}")
            return 1

    def _cmd_analyze_injection(self, args) -> int:
        """Execute the analyze_injection command"""
        try:
            # Lazy import to honor test patches that target 'core.light_core'
            from core.light_core import LightCore  # noqa: WPS433
            # Initialize LightCore - it contains the PromptInjectionAnalyzer instance
            # and the method to call it.
            # This approach is slightly different from other CLI commands that directly
            # instantiate analyzers. Using LightCore centralizes access if the analyzer
            # gains more complex dependencies managed by LightCore.
            core = LightCore()

            print(f"Analyzing prompt for injection (target model: {args.model})...")
            result = core.analyze_prompt_injection(
                target_model_name=args.model, # Changed from model to target_model_name
                prompt_to_test=args.prompt,
                auxiliary_prompts=args.aux_prompts
            )

            print("\n--- Prompt Injection Analysis Result ---")
            print(f"  Injection Detected: {result.get('injection_detected', 'N/A')}")
            print(f"  Confidence Score:   {result.get('confidence_score', 'N/A'):.2f}")
            print(f"  Explanation:        {result.get('explanation', 'N/A')}")
            if result.get('error'):
                print(f"  Error during analysis: {result['error']}")
            print("--- End of Report ---")

            return 0
        except Exception as e:
            logger.error(f"Prompt injection analysis failed: {str(e)}", exc_info=True)
            print(f"Error: Prompt injection analysis failed: {str(e)}")
            return 1

def main():
    """Main entry point for the CLI"""
    cli = StratumCLI()
    sys.exit(cli.run())

if __name__ == "__main__":
    main()
