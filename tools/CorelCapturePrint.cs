// One explicit host-only Corel capture. No printer default changes or laser API.
using System;
using System.Collections.Generic;
using System.IO;
using System.Management;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using VG=Corel.Interop.VGCore;

public static class CorelCapturePrint
{
    const string PrinterName="Aurora JobServer (Test Capture)";
    static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
    static Dictionary<string,object> report=new Dictionary<string,object>();
    static string reportPath;
    static void Save(){File.WriteAllText(reportPath,Json.Serialize(report));}
    static string Hash(string path)
    {using(SHA256 hash=SHA256.Create())using(FileStream file=File.OpenRead(path))return BitConverter.ToString(hash.ComputeHash(file)).Replace("-","").ToLowerInvariant();}
    static void CaptureOnly(string state)
    {
        Dictionary<string,object> status=Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(state,"desktop-status.json")));
        if((string)status["mode"]!="capture_only" || status["session"]!=null || status["current_print"]!=null || (string)status["error"]!="")
            throw new Exception("JobServer must be idle in Capture only. No print submitted.");
    }
    static void LocalPrinter()
    {
        bool found=false;
        using(ManagementObjectSearcher search=new ManagementObjectSearcher("SELECT Name,PortName,DriverName FROM Win32_Printer WHERE Name='Aurora JobServer (Test Capture)'"))
        foreach(ManagementObject printer in search.Get())
        {
            if((string)printer["PortName"]!="AuroraDirect_LPR_Loopback" || (string)printer["DriverName"]!="Aurora JobServer XPS Bridge")
                throw new Exception("Unexpected capture printer driver or port.");
            found=true;
        }
        if(!found)throw new Exception("Capture printer missing.");
        found=false;
        using(ManagementObjectSearcher search=new ManagementObjectSearcher("SELECT HostAddress,PortNumber,Queue,Protocol FROM Win32_TCPIPPrinterPort WHERE Name='AuroraDirect_LPR_Loopback'"))
        foreach(ManagementObject port in search.Get())
        {
            if((string)port["HostAddress"]!="127.0.0.1" || Convert.ToInt32(port["PortNumber"])!=515
                || (string)port["Queue"]!="aurora-direct" || Convert.ToInt32(port["Protocol"])!=2)
                throw new Exception("Capture port is not the expected loopback LPR destination.");
            found=true;
        }
        if(!found)throw new Exception("Loopback capture port missing.");
    }
    public static void VerifyCapturePath(string state) {CaptureOnly(state);LocalPrinter();}
    [STAThread]
    public static int Main(string[] args)
    {
        VG.Application app=null;VG.Document previous=null,doc=null;
        try
        {
            if(args.Length!=4 || (args[3]!="inspect" && args[3]!="submit"))
                throw new ArgumentException("Expected source CDR, new review directory, JobServer state directory, inspect|submit.");
            string source=Path.GetFullPath(args[0]),destination=Path.GetFullPath(args[1]),state=Path.GetFullPath(args[2]);
            if(Directory.Exists(destination))throw new Exception("Review directory exists; preserve prior evidence.");
            string sourceHash=Hash(source);
            bool vector=sourceHash=="ad93dc761fad06199eb89331609d646080dc0d957de2f2d5a8f6531dc65e626c";
            bool mixed=sourceHash=="699a9539c9677ed9257240050c287f7443e88411c49fc6141a4f70e2f8719cf7";
            if(sourceHash!="3ea5256ef14fab3c396ce4a34a566b8d5e21f5b47ec484e18851dd859dbc07be" && !vector && !mixed)
                throw new Exception("Expected a verified color reference.");
            CaptureOnly(state);LocalPrinter();
            Directory.CreateDirectory(destination);reportPath=Path.Combine(destination,"corel-print-report.json");
            string copy=Path.Combine(destination,mixed?"Aurora-Color-Mixed-Capture.cdr":vector?"Aurora-Color-Vector-Capture.cdr":"Aurora-Color-Raster-Capture.cdr");File.Copy(source,copy,false);
            report["source_sha256"]=Hash(source);report["printer"]=PrinterName;report["port"]="127.0.0.1:515/aurora-direct";
            report["reference_kind"]=mixed?"mixed-flat-fills-and-vectors":vector?"vector-colors":"filled-raster-colors";
            report["state"]="opening_owned_copy";report["print_called"]=false;report["physical_device_io"]=false;Save();
            app=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));
            previous=app.ActiveDocument;doc=app.OpenDocument(copy);
            if(doc.Pages.Count!=1 || doc.ActivePage.Shapes.Count!=(mixed?11:6) || Math.Abs(doc.ActivePage.SizeWidth-30)>0.000001
                || Math.Abs(doc.ActivePage.SizeHeight-18)>0.000001)throw new Exception("Reference page/geometry changed.");
            VG.PrintSettings ps=doc.PrintSettings;
            ps.SelectPrinter(PrinterName);ps.PageMatchingMode=VG.PrnPageMatchingMode.prnPageMatchPrinterDefault;
            ps.Layout.Placement=VG.PrnPlaceType.prnPlaceAsInDocument;ps.Layout.PrintTiledPages=false;
            ps.PrintToFile=false;ps.Copies=1;ps.PrintRange=VG.PrnPrintRange.prnWholeDocument;ps.PageSet=VG.PrnPageSet.prnPageSetAll;
            ps.Options.PrintVectors=true;ps.Options.PrintBitmaps=true;ps.Options.PrintText=true;
            ps.Options.RasterizePage=false;ps.Options.UseColorProfile=false;
            ps.Options.ColorMode=VG.PrnColorMode.prnModeFullColor;
            if(ps.Printer.Name!=PrinterName || Math.Abs(ps.PaperWidth-762)>0.001 || Math.Abs(ps.PaperHeight-457.2)>0.001
                || ps.Layout.Placement!=VG.PrnPlaceType.prnPlaceAsInDocument || ps.PrintToFile || ps.Copies!=1)
                throw new Exception("Capture destination/media/placement not verified; no print submitted.");
            report["paper_mm"]=new double[]{ps.PaperWidth,ps.PaperHeight};report["placement"]=ps.Layout.Placement.ToString();
            report["color_mode"]=ps.Options.ColorMode.ToString();report["use_color_profile"]=ps.Options.UseColorProfile;
            report["state"]="verified_before_print";Save();
            if(args[3]=="submit")
            {
                CaptureOnly(state);LocalPrinter();report["state"]="submitting_once";report["print_called"]=true;Save();
                doc.PrintOut();report["state"]="print_call_returned";report["print_call_returned"]=true;Save();
                Console.WriteLine("Submitted exactly one print to the verified local capture queue.");
            }
            else Console.WriteLine("Capture settings verified; inspect mode did not print.");
            return 0;
        }
        catch(Exception ex)
        {
            if(reportPath!=null){report["state"]="error";report["error"]=ex.ToString();Save();}
            Console.Error.WriteLine(ex);return 1;
        }
        finally
        {
            if(doc!=null){if(doc.Dirty)doc.Save();((VG.IVGDocument)doc).Close();}
            if(previous!=null)previous.Activate();
        }
    }
}
