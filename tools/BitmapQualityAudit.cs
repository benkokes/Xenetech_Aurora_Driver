// Read-only native print-provider checks. No queue commit or document printing.
using System;
using System.IO;
using System.Printing;
using System.Printing.Interop;
using System.Collections.Generic;
using System.Web.Script.Serialization;

public static class BitmapQualityAudit
{
    static string Xml(PrintTicket ticket)
    {using(var stream=ticket.GetXmlStream())using(var reader=new StreamReader(stream))return reader.ReadToEnd();}
    [STAThread]
    public static int Main(string[] args)
    {
        if(args.Length!=2 || (args[1]!="before" && args[1]!="verify") || Directory.Exists(args[0]))return 2;
        Directory.CreateDirectory(args[0]);
        var report=new Dictionary<string,object>{{"physical_device_io",false},{"queue_defaults_modified",false}};
        try
        {
            const string printer="Aurora JobServer (Test Capture)";
            using(var server=new LocalPrintServer())using(var queue=server.GetPrintQueue(printer))
            using(var converter=new PrintTicketConverter(printer,1))
            {
                string machine=Xml(queue.DefaultPrintTicket),user=Xml(queue.UserPrintTicket);
                File.WriteAllText(Path.Combine(args[0],"machine.xml"),machine);
                File.WriteAllText(Path.Combine(args[0],"user.xml"),user);
                using(var stream=queue.GetPrintCapabilitiesAsXml())using(var reader=new StreamReader(stream))
                    File.WriteAllText(Path.Combine(args[0],"capabilities.xml"),reader.ReadToEnd());
                var caps=queue.GetPrintCapabilities();
                report["supported_quality"]=caps.OutputQualityCapability;
                report["machine_quality"]=queue.DefaultPrintTicket.OutputQuality;
                report["user_quality"]=queue.UserPrintTicket.OutputQuality;
                if(args[1]=="verify")
                {
                    if(caps.OutputQualityCapability.Count!=1 || caps.OutputQualityCapability[0]!=OutputQuality.High
                        || queue.DefaultPrintTicket.OutputQuality!=OutputQuality.High || queue.UserPrintTicket.OutputQuality!=OutputQuality.High)
                        throw new Exception("Installed provider must advertise and default to High only.");
                    int count=0;
                    foreach(OutputQuality requested in Enum.GetValues(typeof(OutputQuality)))
                    {
                        if(requested==OutputQuality.Unknown)continue;
                        var delta=queue.UserPrintTicket.Clone();delta.OutputQuality=requested;
                        var validated=queue.MergeAndValidatePrintTicket(queue.UserPrintTicket,delta,PrintTicketScope.JobScope).ValidatedPrintTicket;
                        if(validated.OutputQuality!=OutputQuality.High)throw new Exception("Unsupported quality was not normalized: "+requested);
                        byte[] mode=converter.ConvertPrintTicketToDevMode(validated,BaseDevModeType.PrinterDefault);
                        var restored=converter.ConvertDevModeToPrintTicket(mode);
                        if(restored.OutputQuality!=OutputQuality.High)throw new Exception("Lossless quality lost in DEVMODE roundtrip.");
                        File.WriteAllText(Path.Combine(args[0],"roundtrip-"+requested+".xml"),Xml(restored));count++;
                    }
                    if(Xml(queue.DefaultPrintTicket)!=machine || Xml(queue.UserPrintTicket)!=user)throw new Exception("Defaults changed during read-only checks.");
                    report["quality_roundtrips_passed"]=count;
                }
                report["state"]=args[1]=="verify"?"passed":"recorded_before_update";
            }
            return 0;
        }
        catch(Exception error){report["state"]="failed";report["error"]=error.ToString();Console.Error.WriteLine(error);return 1;}
        finally{File.WriteAllText(Path.Combine(args[0],"result.json"),new JavaScriptSerializer().Serialize(report));}
    }
}
