// Owned flat-color acceptance artwork and one LOCAL capture; no device API.
using System;
using System.IO;
using System.Web.Script.Serialization;
using VG=Corel.Interop.VGCore;

public static class CorelMakeColorAcceptance
{
    static VG.Color Color(VG.Application app,int r,int g,int b)
    {var color=app.CreateColor();color.RGBAssign(r,g,b);return color;}
    [STAThread]
    public static int Main(string[] args)
    {
        if(args.Length!=2)return 2;
        try
        {
            string folder=Path.GetFullPath(args[0]),state=Path.GetFullPath(args[1]);
            if(Directory.Exists(folder))throw new Exception("Preserve previous acceptance evidence; choose a new folder.");
            CorelCapturePrint.VerifyCapturePath(state);Directory.CreateDirectory(folder);
            var app=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));
            var doc=app.CreateDocument();doc.Unit=VG.cdrUnit.cdrInch;doc.ActivePage.SetSize(30,18);
            double left=doc.ActivePage.LeftX,top=doc.ActivePage.TopY;
            int[][] colors={new[]{0,0,0},new[]{0,0,128},new[]{0,255,0}};
            string[] labels={"BLACK","NAVY","LIME"};
            for(int i=0;i<3;i++)
            {
                var color=Color(app,colors[i][0],colors[i][1],colors[i][2]);double x=left+1+i;
                var block=doc.ActiveLayer.CreateRectangle2(x,top-1.5,.6,.25);
                block.Name=labels[i]+" fill";block.Outline.SetNoOutline();block.Fill.ApplyUniformFill(color);
                var text=doc.ActiveLayer.CreateArtisticText(0,0,labels[i],Font:"Arial",Size:14,Bold:VG.cdrTriState.cdrTrue);
                text.Name=labels[i]+" lettering";text.Outline.SetNoOutline();text.Fill.ApplyUniformFill(color);
                text.SetPositionEx(VG.cdrReferencePoint.cdrTopLeft,x,top-1);
                // Separated lettering/fill rows exercise zero-exposure row gaps.
            }
            var square=doc.ActiveLayer.CreateRectangle2(left+1,top-2.75,.75,.75);
            square.Name="Red .75in square";square.Fill.ApplyNoFill();square.Outline.Width=.001;
            square.Outline.Color.RGBAssign(255,0,0);
            var circle=doc.ActiveLayer.CreateEllipse2(left+2.375,top-2.375,.375,.375);
            circle.Name="Blue .75in circle";circle.Fill.ApplyNoFill();circle.Outline.Width=.001;
            circle.Outline.Color.RGBAssign(0,0,255);
            var ps=doc.PrintSettings;ps.Reset();ps.SelectPrinter("Aurora JobServer (Test Capture)");
            ps.PageMatchingMode=VG.PrnPageMatchingMode.prnPageMatchPrinterDefault;
            ps.Layout.Placement=VG.PrnPlaceType.prnPlaceAsInDocument;ps.Layout.PrintTiledPages=false;
            ps.PrintToFile=false;ps.Copies=1;ps.Options.PrintVectors=true;ps.Options.PrintText=true;ps.Options.PrintBitmaps=true;
            ps.Options.RasterizePage=false;ps.Options.UseColorProfile=false;ps.Options.ColorMode=VG.PrnColorMode.prnModeFullColor;
            string cdr=Path.Combine(folder,"Aurora-Per-Color-Acceptance.cdr");
            var save=app.CreateStructSaveAsOptions();save.Version=VG.cdrFileVersion.cdrVersion17;doc.SaveAs(cdr,save);
            doc.Activate();app.Visible=true;app.ActiveWindow.ActiveView.ToFitAllObjects();
            // Export just this owned selection as a reference, then clear it.
            var selection=app.CreateShapeRange();foreach(VG.Shape shape in doc.ActivePage.Shapes)selection.Add(shape);
            selection.CreateSelection();
            var export=doc.ExportBitmap(Path.Combine(folder,"reference.png"),VG.cdrFilter.cdrPNG,VG.cdrExportRange.cdrSelection,
                ResolutionX:200,ResolutionY:200,UseColorProfile:false);export.Finish();doc.ClearSelection();
            CorelCapturePrint.VerifyCapturePath(state);
            if(doc.ActivePage.Shapes.Count!=8)throw new Exception("Unexpected test geometry.");
            File.WriteAllText(Path.Combine(folder,"capture-intent.json"),new JavaScriptSerializer().Serialize(new{
                state="submitting_one_local_capture",document=cdr,shape_count=8,physical_device_io=false,
                settings="Current user settings captured only; a separate explicit staged ticket will set acceptance processes."}));
            doc.PrintOut();
            Console.WriteLine("Created and opened per-color artwork; submitted once to Capture only.");return 0;
        }
        catch(Exception e){Console.Error.WriteLine(e);return 1;}
    }
}
