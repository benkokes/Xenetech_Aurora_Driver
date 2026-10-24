// Create an owned printable sheet: grayscale bitmap plus two true vector paths.
// Does not print or alter printer defaults; leaves the resulting document open.
using System;
using System.IO;
using System.Web.Script.Serialization;
using VG=Corel.Interop.VGCore;

public static class CorelMakePrintableSheet
{
    [STAThread]
    public static int Main(string[] args)
    {
        if(args.Length!=2 || !File.Exists(args[0]) || File.Exists(args[1]))return 2;
        VG.Document doc=null,previous=null;bool success=false;
        try
        {
            var app=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));
            previous=app.ActiveDocument;string previousName=previous==null?null:previous.FullFileName;
            doc=app.CreateDocument();doc.Unit=VG.cdrUnit.cdrInch;doc.ActivePage.SetSize(30,18);
            var import=doc.ActiveLayer.ImportEx(Path.GetFullPath(args[0]),VG.cdrFilter.cdrBMP,null);import.Finish();
            if(doc.ActivePage.Shapes.Count!=1)throw new Exception("Expected one imported raster.");
            var bitmap=doc.ActivePage.Shapes[1];bitmap.Name="Accepted 54 percent raster panels";
            double left=doc.ActivePage.LeftX+1,top=doc.ActivePage.TopY-1;
            bitmap.SetSize(4,3);bitmap.SetPositionEx(VG.cdrReferencePoint.cdrTopLeft,left,top);
            var square=doc.ActiveLayer.CreateRectangle2(left+16.0/167,top-485.0/167,1,1);
            var circle=doc.ActiveLayer.CreateEllipse2(left+548.0/167,top-400.0/167,250.0/1002,250.0/1002,0,360,false);
            var paths=app.CreateShapeRange();paths.Add(square);paths.Add(circle);
            var outlines=paths.Combine();outlines.Name="Square and circle - vector engraving";
            outlines.Fill.ApplyNoFill();outlines.Outline.Width=.001;outlines.Outline.Color.RGBAssign(255,0,0);
            if(doc.ActivePage.Shapes.Count!=2 || outlines.Curve.SubPaths.Count!=2)
                throw new Exception("Expected a bitmap and one two-path vector curve.");
            var ps=doc.PrintSettings;ps.Reset();ps.SelectPrinter("Aurora JobServer (Test Capture)");
            ps.PageMatchingMode=VG.PrnPageMatchingMode.prnPageMatchPrinterDefault;
            ps.Layout.Placement=VG.PrnPlaceType.prnPlaceAsInDocument;ps.Layout.PrintTiledPages=false;
            ps.PrintToFile=false;ps.Copies=1;
            ps.Options.PrintVectors=true;ps.Options.PrintBitmaps=true;ps.Options.PrintText=true;
            ps.Options.RasterizePage=false;ps.Options.UseColorProfile=false;ps.Options.ColorMode=VG.PrnColorMode.prnModeFullColor;
            var options=app.CreateStructSaveAsOptions();options.Version=VG.cdrFileVersion.cdrVersion17;
            doc.SaveAs(Path.GetFullPath(args[1]),options);doc.ClearSelection();doc.Activate();app.Visible=true;
            app.ActiveWindow.ActiveView.ToFitAllObjects();
            File.WriteAllText(args[1]+".json",new JavaScriptSerializer().Serialize(new {
                state="printable_sheet_open_in_X7",document=doc.FullFileName,previous_document=previousName,
                shape_count=doc.ActivePage.Shapes.Count,vector_subpaths=outlines.Curve.SubPaths.Count,
                bitmap_inches=new[]{bitmap.SizeWidth,bitmap.SizeHeight},page_inches=new[]{30,18},
                printer=ps.Printer.Name,paper_mm=new[]{ps.PaperWidth,ps.PaperHeight},
                placement=ps.Layout.Placement.ToString(),print_called=false,printer_defaults_changed=false,
                dither_panels="preprocessed raster artwork; global Dither Bitmaps remains off"
            }));
            success=true;Console.WriteLine("Printable raster/vector sheet is open in X7.");return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
        finally{if(!success){if(doc!=null)((VG.IVGDocument)doc).Close();if(previous!=null)previous.Activate();}}
    }
}
