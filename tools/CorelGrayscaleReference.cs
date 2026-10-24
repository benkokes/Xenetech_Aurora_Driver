// Owned offline fixture only. Does not print or change printer preferences.
using System;
using System.IO;
using System.Web.Script.Serialization;
using VG=Corel.Interop.VGCore;

public static class CorelGrayscaleReference
{
    [STAThread]
    public static int Main(string[] args)
    {
        if(args.Length!=2 || File.Exists(args[1]))return 2;
        VG.Document doc=null,previous=null;
        try
        {
            var app=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));
            previous=app.ActiveDocument;doc=app.CreateDocument();doc.Unit=VG.cdrUnit.cdrInch;
            doc.ActivePage.SetSize(30,18);
            var filter=doc.ActiveLayer.ImportEx(Path.GetFullPath(args[0]),VG.cdrFilter.cdrBMP,null);filter.Finish();
            if(doc.ActivePage.Shapes.Count!=1)throw new Exception("Expected one imported bitmap.");
            var bitmap=doc.ActivePage.Shapes[1];bitmap.SetSize(4,2);
            bitmap.SetPositionEx(VG.cdrReferencePoint.cdrTopLeft,doc.ActivePage.LeftX+1,doc.ActivePage.TopY-1);
            var marker=doc.ActiveLayer.CreateRectangle2(doc.ActivePage.LeftX+5.2,doc.ActivePage.TopY-1.5,.25,.5);
            marker.Fill.ApplyNoFill();marker.Outline.Width=.003;marker.Outline.Color.RGBAssign(255,0,0);
            var options=app.CreateStructSaveAsOptions();options.Version=VG.cdrFileVersion.cdrVersion11;
            doc.SaveAs(Path.GetFullPath(args[1]),options);
            File.WriteAllText(args[1]+".json",new JavaScriptSerializer().Serialize(new {
                state="owned_Corel11_compatible_reference_created", shapes=doc.ActivePage.Shapes.Count,
                page_inches=new[]{doc.ActivePage.SizeWidth,doc.ActivePage.SizeHeight},
                bitmap_inches=new[]{bitmap.SizeWidth,bitmap.SizeHeight},
                physical_device_io=false, print_called=false }));
            return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
        finally{if(doc!=null)((VG.IVGDocument)doc).Close();if(previous!=null)previous.Activate();}
    }
}
