# Tutorial: Create a Revit Design Automation Addin

**Example: Global Parameters Addin** - Reads JSON and updates Revit Global Parameters automatically

---

## Prerequisites

**Install Visual Studio Community** (free): https://visualstudio.microsoft.com/vs/community/
- Select ".NET desktop development" workload during installation

---

## Step 1: Create New Project

First, let's create a new C# project that will hold your addin code.

1. Open Visual Studio → **File** → **New** → **Project**
2. Select **Class Library (.NET Framework)**
3. Name: `GlobalParametersDA`
4. Framework: **.NET Framework 4.8**

---

## Step 2: Add References

Now you need to tell your project about the Revit API and JSON library it will use.

### Via NuGet (Right-click project → Manage NuGet Packages)

Install these packages:
- `Newtonsoft.Json` (latest)
- `Autodesk.Forge.DesignAutomation.Revit` (version `2024.0.0` for Revit 2024)

### Alternative: Manual DLLs

If NuGet doesn't have your Revit version:
1. Right-click **References** → **Add Reference** → **Browse**
2. From `C:\Program Files\Autodesk\Revit 2024\` add:
   - `RevitAPI.dll`
   - `DesignAutomationBridge.dll`
3. Set **Copy Local = False** for Revit DLLs (they're provided by Design Automation)

---

## Step 3: Write the Code

Time to write the actual logic. This code reads a JSON file and updates Global Parameters in your Revit model.

Rename `Class1.cs` to `GlobalParametersDA.cs`:

```csharp
// File: GlobalParametersDA.cs
// This addin reads global_params.json and updates Revit Global Parameters

using System;
using System.Globalization;
using System.IO;
using Autodesk.Revit.ApplicationServices;
using Autodesk.Revit.DB;
using DesignAutomationFramework;
using Newtonsoft.Json.Linq;

namespace GlobalParametersDA
{
    public class App : IExternalDBApplication
    {
        private const string JsonLocalName = "global_params.json";

        public ExternalDBApplicationResult OnStartup(ControlledApplication app)
        {
            DesignAutomationBridge.DesignAutomationReadyEvent += OnDesignAutomationReady;
            return ExternalDBApplicationResult.Succeeded;
        }

        public ExternalDBApplicationResult OnShutdown(ControlledApplication app)
        {
            DesignAutomationBridge.DesignAutomationReadyEvent -= OnDesignAutomationReady;
            return ExternalDBApplicationResult.Succeeded;
        }

        private void OnDesignAutomationReady(object sender, DesignAutomationReadyEventArgs e)
        {
            try
            {
                Run(e.DesignAutomationData);
                e.Succeeded = true;
            }
            catch (Exception ex)
            {
                Console.WriteLine("DA ERROR: " + ex);
                e.Succeeded = false;
            }
        }

        private static void Run(DesignAutomationData data)
        {
            if (data == null) throw new ArgumentNullException(nameof(data));
            Application rvtApp = data.RevitApp ?? throw new InvalidOperationException("RevitApp is null.");
            Document doc = data.RevitDoc ?? throw new InvalidOperationException("RevitDoc is null.");

            string wd = Directory.GetCurrentDirectory();
            string jsonPath = Path.Combine(wd, JsonLocalName);

            Console.WriteLine("DA: Working folder: " + wd);
            Console.WriteLine("DA: Looking for: " + jsonPath);

            if (!File.Exists(jsonPath))
            {
                Console.WriteLine("DA: JSON not found, no changes applied.");
                SaveResult(doc);
                return;
            }

            JObject root;
            try
            {
                root = JObject.Parse(File.ReadAllText(jsonPath));
                Console.WriteLine("DA: Parsed " + JsonLocalName);
            }
            catch (Exception ex)
            {
                Console.WriteLine("DA: Invalid JSON, " + ex.Message);
                SaveResult(doc);
                return;
            }

            if (!GlobalParametersManager.AreGlobalParametersAllowed(doc))
            {
                Console.WriteLine("DA: Global Parameters not supported in this document.");
                SaveResult(doc);
                return;
            }

            int updated = 0, skipped = 0, missing = 0, errors = 0;

            using (Transaction tx = new Transaction(doc, "Set Global Parameters from JSON"))
            {
                tx.Start();

                foreach (var prop in root.Properties())
                {
                    string gpName = prop.Name;
                    JToken valTok = prop.Value;

                    // Only numeric inputs are supported
                    if (!IsNumericToken(valTok))
                    {
                        skipped++;
                        Console.WriteLine($"DA: Skip {gpName}, non numeric value.");
                        continue;
                    }

                    ElementId gpId = GlobalParametersManager.FindByName(doc, gpName);
                    if (gpId == ElementId.InvalidElementId)
                    {
                        missing++;
                        Console.WriteLine($"DA: Skip {gpName}, global parameter not found.");
                        continue;
                    }

                    GlobalParameter gp = doc.GetElement(gpId) as GlobalParameter;
                    if (gp == null)
                    {
                        errors++;
                        Console.WriteLine($"DA: Skip {gpName}, invalid element id.");
                        continue;
                    }

                    // Do not overwrite reporting or formula driven parameters
                    if (gp.IsReporting || gp.IsDrivenByFormula)
                    {
                        skipped++;
                        Console.WriteLine($"DA: Skip {gpName}, reporting or formula driven.");
                        continue;
                    }

                    try
                    {
                        ParameterValue pval = BuildParameterValue(doc, gp, valTok);
                        gp.SetValue(pval);
                        updated++;
                        Console.WriteLine($"DA: Set {gpName}");
                    }
                    catch (Exception ex)
                    {
                        errors++;
                        Console.WriteLine($"DA: Failed {gpName}, {ex.Message}");
                    }
                }

                tx.Commit();
            }

            Console.WriteLine($"DA: Summary, Updated {updated}, Missing {missing}, Skipped {skipped}, Errors {errors}");
            SaveResult(doc);
        }

        private static void SaveResult(Document doc)
        {
            try
            {
                // Always write a new file named result.rvt in the working folder
                var sao = new SaveAsOptions { OverwriteExistingFile = true };
                string outPath = Path.Combine(Directory.GetCurrentDirectory(), "result.rvt");
                doc.SaveAs(outPath, sao);
                Console.WriteLine("DA: Saved result.rvt");
            }
            catch (Exception ex)
            {
                Console.WriteLine("DA: Save failed, " + ex.Message);
                throw;
            }
        }

        private static bool IsNumericToken(JToken t)
        {
            return t != null &&
                   (t.Type == JTokenType.Integer ||
                    t.Type == JTokenType.Float ||
                    (t.Type == JTokenType.String && double.TryParse((string)t, NumberStyles.Float, CultureInfo.InvariantCulture, out _)));
        }

        /// <summary>
        /// Build a ParameterValue for a Global Parameter based on its definition data type.
        /// Integers use IntegerParameterValue.
        /// SpecTypeId.Number uses DoubleParameterValue with the raw number.
        /// Measurable specs, for example Length, Area, Angle, Volume, convert from the project's display unit to internal.
        /// </summary>
        private static ParameterValue BuildParameterValue(Document doc, GlobalParameter gp, JToken valueTok)
        {
            if (valueTok == null) throw new InvalidOperationException("Missing value.");

            // ParameterElement.GetDefinition() -> Definition.GetDataType() gives the spec id (ForgeTypeId)
            Definition def = gp.GetDefinition();
            ForgeTypeId spec = def.GetDataType();

            // Integer global parameters
            if (spec == SpecTypeId.Int.Integer)
            {
                int ival = valueTok.Type == JTokenType.Integer
                    ? (int)valueTok
                    : Convert.ToInt32(ToDouble(valueTok), CultureInfo.InvariantCulture);
                return new IntegerParameterValue(ival);
            }

            // Plain number (unitless)
            if (spec == SpecTypeId.Number)
            {
                double dval = ToDouble(valueTok);
                return new DoubleParameterValue(dval);
            }

            // Measurable spec, convert from document display unit to internal
            if (UnitUtils.IsMeasurableSpec(spec))
            {
                double displayVal = ToDouble(valueTok);

                Units units = doc.GetUnits();
                FormatOptions fo = units.GetFormatOptions(spec);
                ForgeTypeId displayUnit = fo.GetUnitTypeId();

                double internalVal = UnitUtils.ConvertToInternalUnits(displayVal, displayUnit);
                return new DoubleParameterValue(internalVal);
            }

            throw new InvalidOperationException($"Unsupported data type '{spec?.TypeId}' for global parameter '{gp.Name}'.");
        }

        private static double ToDouble(JToken t)
        {
            if (t.Type == JTokenType.Integer) return Convert.ToDouble((int)t, CultureInfo.InvariantCulture);
            if (t.Type == JTokenType.Float) return (double)t;
            if (t.Type == JTokenType.String) return double.Parse((string)t, CultureInfo.InvariantCulture);
            throw new InvalidOperationException($"Value '{t}' is not numeric.");
        }
    }
}

```

---

## Step 4: Build the DLL

Compile your code into a DLL file that Revit can load.

1. **Build** → **Build Solution** (or `Ctrl+Shift+B`)
2. Find your DLL at `bin\Debug\GlobalParametersDA.dll`

---

## Step 5: Create the Bundle Package

Package your DLL with configuration files so Design Automation knows how to run it.

### Bundle Structure

```bash
GlobalParametersDA.bundle\
│   PackageContents.xml
│
└───Contents
        GlobalParametersDA.addin
        GlobalParametersDA.dll
        Newtonsoft.Json.dll
```

**Copy these files:**
- `GlobalParametersDA.dll` from `bin\Debug\`
- `Newtonsoft.Json.dll` from `bin\Debug\`
- Create the XML files below

### PackageContents.xml

```xml
<?xml version="1.0" encoding="utf-8"?>
<ApplicationPackage
  SchemaVersion="1.0"
  AutodeskProduct="Revit"
  Name="GlobalParametersDA"
  AppVersion="1.0.0">
  <Components>
    <Component
      Name="GlobalParametersDA"
      AppId="GlobalParametersDA"
      ModuleName="./Contents/GlobalParametersDA.dll"
      AppType="RevitPlugin">
      <RuntimeRequirements OS="Windows" Platform="x64" SeriesMin="R2024" SeriesMax="R2024"/>
      <RevitAddIn Type="DBApplication">
        <Assembly>Contents\GlobalParametersDA.dll</Assembly>
        <FullClassName>GlobalParametersDA.App</FullClassName>
        <AddInId>{9F47B1C9-FF59-4F6C-B2B8-1D3D2A7D9F11}</AddInId>
      </RevitAddIn>
    </Component>
  </Components>
</ApplicationPackage>

```

### GlobalParametersDA.addin

```xml
<?xml version="1.0" encoding="utf-8"?>
<RevitAddIns>
  <AddIn Type="DBApplication">
    <Name>GlobalParametersDA</Name>
    <Assembly>.\GlobalParametersDA.dll</Assembly>
    <FullClassName>GlobalParametersDA.App</FullClassName>
    <AddInId>9f47b1c9-ff59-4f6c-b2b8-1d3d2a7d9f11</AddInId>
    <VendorId>VKT</VendorId>
    <VendorDescription>VIKTOR</VendorDescription>
  </AddIn>
</RevitAddIns>
```

---

## Step 6: Package and Upload

Finally, zip everything up and upload it to APS Design Automation.

1. Zip the entire `GlobalParametersDA.bundle` folder
2. Upload to APS Design Automation as an AppBundle


