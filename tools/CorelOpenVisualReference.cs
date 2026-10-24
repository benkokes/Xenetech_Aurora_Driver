// Open an owned comparison PNG in X7. No printing or printer-setting access.
using System;
using System.IO;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using VG=Corel.Interop.VGCore;

public static class CorelOpenVisualReference
{
    static string Hash(string path){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();}
    [STAThread]
    public static int Main(string[] args)
    {
        if(args.Length!=2 || !File.Exists(args[0]) || File.Exists(args[1]) || File.Exists(args[1]+".json"))return 2;
        VG.Document doc=null,previous=null;bool success=false;
        try
        {
            string source=Path.GetFullPath(args[0]),target=Path.GetFullPath(args[1]);
            var app=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));
            previous=app.ActiveDocument;
            string previousName=previous==null?null:previous.FullFileName;
            doc=app.CreateDocument();doc.Unit=VG.cdrUnit.cdrInch;doc.ActivePage.SetSize(30,18);
            var filter=doc.ActiveLayer.ImportEx(source,VG.cdrFilter.cdrPNG,null);filter.Finish();
            if(doc.ActivePage.Shapes.Count!=1)throw new Exception("Expected one imported comparison bitmap.");
            var bitmap=doc.ActivePage.Shapes[1];bitmap.Name="VISUAL COMPARISON IMAGE";
            bitmap.SetSize(4.008,3.006);
            bitmap.SetPositionEx(VG.cdrReferencePoint.cdrTopLeft,doc.ActivePage.LeftX+1.002,doc.ActivePage.TopY-1.002);
            var options=app.CreateStructSaveAsOptions();options.Version=VG.cdrFileVersion.cdrVersion17;
            doc.SaveAs(target,options);doc.ClearSelection();doc.Activate();app.Visible=true;
            app.ActiveWindow.ActiveView.ToFitShape(bitmap);
            if(!String.Equals(app.ActiveDocument.FullFileName,target,StringComparison.OrdinalIgnoreCase))
                throw new Exception("Comparison document did not become active.");
            File.WriteAllText(target+".json",new JavaScriptSerializer().Serialize(new {
                state="comparison_image_open_in_X7",source=source,source_sha256=Hash(source),
                document=target,document_sha256=Hash(target),previous_document=previousName,
                page_inches=new[]{doc.ActivePage.SizeWidth,doc.ActivePage.SizeHeight},
                image_inches=new[]{bitmap.SizeWidth,bitmap.SizeHeight},
                previous_document_left_open=previous!=null,print_called=false,printer_settings_changed=false,
                reference_kind="single bitmap visual reference; red vector marks are included in its preview pixels"
            }));
            success=true;Console.WriteLine("Opened comparison image in CorelDRAW X7: "+target);return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
        finally{if(!success){if(doc!=null)((VG.IVGDocument)doc).Close();if(previous!=null)previous.Activate();}}
    }
}
