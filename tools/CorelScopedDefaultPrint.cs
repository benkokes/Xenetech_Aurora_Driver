// One real Corel capture, with backed-up/restored per-user test-printer settings.
// No installed-driver changes, machine defaults, default-printer switch or device API.
using System;
using System.Collections.Generic;
using System.IO;
using System.Printing;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Xml;
using Aurora.Frontend;
using VG=Corel.Interop.VGCore;

public static class CorelScopedDefaultPrint
{
    static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
    static string Xml(PrintTicket ticket){using(var s=ticket.GetXmlStream())using(var r=new StreamReader(s))return r.ReadToEnd();}
    static PrintTicket Ticket(string text){using(var stream=new MemoryStream(Encoding.UTF8.GetBytes(text)))return new PrintTicket(stream);}
    static string Full(string baseline,ClassicSettings selected)
    {dynamic dom=Activator.CreateInstance(Type.GetTypeFromProgID("Msxml2.DOMDocument.6.0"));dom.async=false;if(!(bool)dom.loadXML(baseline))throw new Exception("Invalid baseline ticket.");ClassicTicket.WriteFullNative(dom,selected);return (string)dom.xml;}
    static void Write(string path,Dictionary<string,object> report){File.WriteAllText(path,Json.Serialize(report));}
    [DllImport("winspool.drv",CharSet=CharSet.Unicode,SetLastError=true)]static extern bool OpenPrinter(string name,out IntPtr handle,IntPtr defaults);
    [DllImport("winspool.drv",CharSet=CharSet.Unicode,SetLastError=true)]static extern bool SetPrinter(IntPtr handle,int level,IntPtr info,int command);
    [DllImport("winspool.drv")]static extern bool ClosePrinter(IntPtr handle);
    static void RestoreUserSnapshot(string original)
    {
        var xml=new XmlDocument {XmlResolver=null};
        using(var reader=XmlReader.Create(new StringReader(original),new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=1024*1024}))xml.Load(reader);
        byte[] mode=null;
        foreach(XmlElement parameter in xml.GetElementsByTagName("ParameterInit",ClassicTicket.Framework))
        {
            string[] name=parameter.GetAttribute("name").Split(':');
            if(name.Length==2 && name[1]=="PageDevmodeSnapshot" && parameter.GetNamespaceOfPrefix(name[0])==ClassicTicket.Private)
                mode=Convert.FromBase64String(parameter.InnerText);
        }
        if(mode==null || mode.Length<220 || BitConverter.ToUInt16(mode,68)!=220
            || 220+BitConverter.ToUInt16(mode,70)!=mode.Length
            || Encoding.Unicode.GetString(mode,0,64).TrimEnd('\0')!="Aurora JobServer (Test Capture)")
            throw new Exception("Original per-user DEVMODE snapshot is not the expected test printer.");
        IntPtr handle,buffer=IntPtr.Zero,info=IntPtr.Zero;
        if(!OpenPrinter("Aurora JobServer (Test Capture)",out handle,IntPtr.Zero))throw new Win32Exception();
        try
        {
            buffer=Marshal.AllocHGlobal(mode.Length);Marshal.Copy(mode,0,buffer,mode.Length);
            info=Marshal.AllocHGlobal(IntPtr.Size);Marshal.WriteIntPtr(info,buffer);
            if(!SetPrinter(handle,9,info,0))throw new Win32Exception();
        }
        finally{if(info!=IntPtr.Zero)Marshal.FreeHGlobal(info);if(buffer!=IntPtr.Zero)Marshal.FreeHGlobal(buffer);ClosePrinter(handle);}
    }
    [STAThread]
    public static int Main(string[] args)
    {
        if(args.Length==4 && (args[0]=="--restore-user" || args[0]=="--audit-user"))
        {
            try{
            if(File.Exists(args[2]))throw new Exception("Choose a fresh exact-restoration evidence file.");
            CorelCapturePrint.VerifyCapturePath(Path.GetFullPath(args[3]));
            string original=File.ReadAllText(args[1]);if(args[0]=="--restore-user")RestoreUserSnapshot(original);
            using(var server=new LocalPrintServer())using(var queue=server.GetPrintQueue("Aurora JobServer (Test Capture)"))
            {
                string restored=Xml(queue.UserPrintTicket);File.WriteAllText(args[2],restored);
                if(restored!=original)throw new Exception("Exact user snapshot restoration differs; preserve evidence.");
            }
            Console.WriteLine(args[0]=="--restore-user"?"Original per-user snapshot restored byte-for-byte.":"Read-only audit: original per-user snapshot still byte-identical.");return 0;
            }catch(Exception error){Console.Error.WriteLine(error);return 1;}
        }
        if((args.Length!=4 && args.Length!=5) || Directory.Exists(args[3]))return 2;
        bool qualityHigh=args.Length==5 && args[4]=="--quality-high";
        if(args.Length==5 && !qualityHigh)throw new ArgumentException("Unknown image-quality test option.");
        string source=Path.GetFullPath(args[0]),expected=Path.GetFullPath(args[1]),state=Path.GetFullPath(args[2]),root=Path.GetFullPath(args[3]);
        ClassicSettings selected=ClassicSettings.FromXml(File.ReadAllText(expected));
        if(selected.Autostart || selected.Resolution!=167)throw new Exception("Scoped test requires Autostart Off and 167 DPI.");
        CorelCapturePrint.VerifyCapturePath(state);
        Directory.CreateDirectory(root);File.WriteAllText(Path.Combine(root,"expected.xml"),selected.ToXml());
        string reportPath=Path.Combine(root,"result.json");
        var report=new Dictionary<string,object>{{"state","initializing"},{"print_called",false},{"physical_device_io",false},
            {"settings_scope","temporary per-user test-printer defaults, restored in finally"}};
        int result=1;VG.Document doc=null,previous=null;
        using(var server=new LocalPrintServer())using(var queue=server.GetPrintQueue("Aurora JobServer (Test Capture)"))
        {
            string machine=Xml(queue.DefaultPrintTicket),user=Xml(queue.UserPrintTicket);
            File.WriteAllText(Path.Combine(root,"queue-before.xml"),machine);File.WriteAllText(Path.Combine(root,"user-before.xml"),user);
            try
            {
                if(queue.NumberOfJobs!=0)throw new Exception("Capture printer is not empty.");
                var validated=queue.MergeAndValidatePrintTicket(queue.UserPrintTicket,Ticket(Full(user,selected)),PrintTicketScope.JobScope).ValidatedPrintTicket;
                if(qualityHigh)
                {
                    validated.OutputQuality=OutputQuality.High;
                    validated=queue.MergeAndValidatePrintTicket(queue.UserPrintTicket,validated,PrintTicketScope.JobScope).ValidatedPrintTicket;
                    if(validated.OutputQuality!=OutputQuality.High)throw new Exception("Provider does not retain requested High output quality; no print submitted.");
                    report["requested_output_quality"]="High";
                }
                if(ClassicTicket.Read(Xml(validated),ClassicTicket.Selection(Xml(validated))).ToXml()!=selected.ToXml())throw new Exception("Native validation changed settings.");
                queue.UserPrintTicket=validated;queue.Commit();queue.Refresh();
                string applied=Xml(queue.UserPrintTicket);File.WriteAllText(Path.Combine(root,"user-applied.xml"),applied);
                if(ClassicTicket.Read(applied,ClassicTicket.Selection(applied)).ToXml()!=selected.ToXml())throw new Exception("Per-user test settings not applied.");
                if(qualityHigh && queue.UserPrintTicket.OutputQuality!=OutputQuality.High)throw new Exception("High output quality did not survive native defaults; no print submitted.");
                var app=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));previous=app.ActiveDocument;
                string owned=Path.Combine(root,"Owned-Feature-Reference.cdr");File.Copy(source,owned,false);doc=app.OpenDocument(owned);
                if(doc.Pages.Count!=1 || doc.ActivePage.Shapes.Count!=2 || doc.ActivePage.SizeWidth!=30 || doc.ActivePage.SizeHeight!=18)throw new Exception("Unexpected owned artwork.");
                var ps=doc.PrintSettings;ps.Reset();ps.SelectPrinter("Aurora JobServer (Test Capture)");
                ps.PageMatchingMode=VG.PrnPageMatchingMode.prnPageMatchPrinterDefault;ps.Layout.Placement=VG.PrnPlaceType.prnPlaceAsInDocument;
                ps.Layout.PrintTiledPages=false;ps.PrintToFile=false;ps.Copies=1;ps.PrintRange=VG.PrnPrintRange.prnWholeDocument;
                ps.Options.PrintVectors=true;ps.Options.PrintBitmaps=true;ps.Options.PrintText=true;ps.Options.RasterizePage=false;
                ps.Options.UseColorProfile=false;ps.Options.ColorMode=VG.PrnColorMode.prnModeFullColor;
                if(ps.Printer.Name!="Aurora JobServer (Test Capture)" || Math.Abs(ps.PaperWidth-762)>.001 || Math.Abs(ps.PaperHeight-457.2)>.001)throw new Exception("Unexpected print destination/media.");
                var before=new HashSet<string>(Directory.GetDirectories(Path.Combine(state,"capture-only")));
                CorelCapturePrint.VerifyCapturePath(state);report["state"]="submitting_once";report["print_called"]=true;Write(reportPath,report);
                doc.PrintOut();
                DateTime deadline=DateTime.UtcNow.AddSeconds(15);var captures=new List<string>();
                while(DateTime.UtcNow<deadline)
                {
                    captures.Clear();foreach(string folder in Directory.GetDirectories(Path.Combine(state,"capture-only")))
                    {
                        // capture.json is written inside .receiving-ID before
                        // the receiver atomically publishes the UUID folder.
                        Guid publishedId;
                        if(Guid.TryParseExact(Path.GetFileName(folder),"D",out publishedId)
                            && !before.Contains(folder) && File.Exists(Path.Combine(folder,"capture.json")))captures.Add(folder);
                    }
                    if(captures.Count>0)break;Thread.Sleep(100);
                }
                if(captures.Count!=1)throw new Exception("Expected exactly one complete capture; do not resubmit.");
                report["capture_id"]=Path.GetFileName(captures[0]);report["capture_directory"]=captures[0];report["state"]="captured_pending_independent_settings_check";result=0;
            }
            catch(Exception error){report["state"]="failed";report["error"]=error.ToString();Console.Error.WriteLine(error);}
            finally
            {
                try
                {
                    RestoreUserSnapshot(user);queue.Refresh();
                    string restored=Xml(queue.UserPrintTicket);File.WriteAllText(Path.Combine(root,"user-restored.xml"),restored);
                    report["machine_defaults_unchanged"]=Xml(queue.DefaultPrintTicket)==machine;
                    report["user_defaults_byte_identical"]=restored==user;
                    if(!(bool)report["machine_defaults_unchanged"] || !(bool)report["user_defaults_byte_identical"])throw new Exception("Default restoration needs inspection.");
                    report["defaults_restored"]=true;
                }
                catch(Exception error){result=1;report["restore_error"]=error.ToString();Console.Error.WriteLine(error);}
                try
                {
                    if(doc!=null){if(doc.Dirty)doc.Save();((VG.IVGDocument)doc).Close();}
                    if(previous!=null)previous.Activate();
                }
                catch(Exception error){result=1;report["owned_document_cleanup_error"]=error.ToString();Console.Error.WriteLine(error);}
                Write(reportPath,report);
            }
        }
        return result;
    }
}
