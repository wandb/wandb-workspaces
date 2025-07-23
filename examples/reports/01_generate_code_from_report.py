"""
Example: Generate code from existing W&B reports

This example demonstrates how to use the to_code() feature to reverse-engineer
existing W&B reports and generate the Python code needed to recreate them.
"""

import wandb_workspaces.reports.v2 as wr

def main():
    # Example 1: Generate code from a report URL
    print("Example 1: Loading a report from URL and generating code")
    print("=" * 60)
    
    # Replace this with your own report URL
    report_url = "https://wandb.ai/your-entity/your-project/reports/Your-Report--VmlldzoxMjM0NTY3OA"
    
    try:
        # Load the report
        report = wr.Report.from_url(report_url)
        print(f"Loaded report: {report.title}")
        
        # Generate code
        code = report.to_code()
        
        # Print the generated code
        print("\nGenerated code:")
        print("-" * 40)
        print(code)
        print("-" * 40)
        
    except Exception as e:
        print(f"Note: Could not load report from URL. Error: {e}")
        print("Make sure you have access to the report and are logged in to W&B.")
    
    # Example 2: Generate code from a locally created report
    print("\n\nExample 2: Creating a report and generating its code")
    print("=" * 60)
    
    # Create a sample report
    report = wr.Report(
        project="my-project",
        entity="my-entity",
        title="Sample Performance Report",
        description="A report showing model performance metrics"
    )
    
    # Add some content
    report.blocks = [
        wr.H1("Model Performance"),
        wr.P("This report tracks key metrics during training."),
        wr.PanelGrid(
            panels=[
                wr.LinePlot(
                    x="Step",
                    y=["train/loss", "val/loss"],
                    title="Training and Validation Loss"
                ),
                wr.ScatterPlot(
                    x="epoch",
                    y="accuracy",
                    title="Accuracy per Epoch"
                ),
                wr.BarPlot(
                    metrics=["final_f1_score"],
                    orientation="h",
                    title="Final F1 Score"
                )
            ]
        ),
        wr.H2("Configuration"),
        wr.CodeBlock(
            code="learning_rate: 0.001\nbatch_size: 32\nmodel: ResNet50",
            language="yaml"
        )
    ]
    
    # Generate code for this report
    code = report.to_code()
    
    print("Generated code for the sample report:")
    print("-" * 40)
    print(code)
    print("-" * 40)
    
    # Save the generated code to a file
    with open("generated_report_code.py", "w") as f:
        f.write(code)
    print("\nGenerated code saved to: generated_report_code.py")
    
    # Example 3: Handling reports with custom metrics
    print("\n\nExample 3: Report with custom metric types")
    print("=" * 60)
    
    report_custom = wr.Report(
        project="my-project",
        entity="my-entity",
        title="Advanced Metrics Report"
    )
    
    report_custom.blocks = [
        wr.PanelGrid(
            panels=[
                wr.LinePlot(
                    x=wr.Metric("Step"),
                    y=[wr.Metric("custom/metric1"), wr.Metric("custom/metric2")],
                    groupby=wr.Config("model_type"),
                    aggregate=True
                ),
                wr.BarPlot(
                    metrics=[wr.SummaryMetric("best_score")],
                    groupby=wr.Config("dataset"),
                    aggregate=True
                )
            ]
        )
    ]
    
    code_custom = report_custom.to_code()
    print("Generated code with custom metrics:")
    print("-" * 40)
    print(code_custom)
    print("-" * 40)

if __name__ == "__main__":
    print("W&B Reports: to_code() Feature Example")
    print("=" * 80)
    print("\nThis example shows how to generate Python code from W&B reports.")
    print("The to_code() method allows you to:")
    print("- Reverse-engineer existing reports")
    print("- Learn the report API by examining real examples")
    print("- Create templates from existing reports")
    print("- Version control report configurations\n")
    
    main()
    
    print("\n" + "=" * 80)
    print("Example complete!")
    print("You can now use the generated code to recreate reports programmatically.")