// Create and open owned test artwork. No PrintOut or printer-default writes.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Web.Script.Serialization;
using VG=Corel.Interop.VGCore;

public static class CorelMakeMixedTest
{
    static double D(Dictionary<string,object> o,string key){return Convert.ToDouble(o[key],CultureInfo.InvariantCulture);}
    static bool B(Dictionary<string,object> o,string key){return o.ContainsKey(key) && Convert.ToBoolean(o[key]);}
    static void Preview(VG.Application app,VG.Document doc,string path)
    {
        VG.Shape background=null;
        try
        {
            double left=doc.ActivePage.LeftX+1,top=doc.ActivePage.TopY-1;
            background=doc.ActiveLayer.CreateRectangle2(left-.1,top-4.7,6.25,4.85);
            VG.Color white=app.CreateColor();white.RGBAssign(255,255,255);
            background.Outline.SetNoOutline();background.Fill.ApplyUniformFill(white);background.OrderToBack();
            var selected=app.CreateShapeRange();foreach(VG.Shape shape in doc.ActivePage.Shapes)selected.Add(shape);
            selected.CreateSelection();
            var export=doc.ExportBitmap(path,VG.cdrFilter.cdrPNG,VG.cdrExportRange.cdrSelection,
                ResolutionX:200,ResolutionY:200,UseColorProfile:false);export.Finish();
        }
        finally{if(background!=null)background.Delete();doc.ClearSelection();}
    }
    [STAThread]
    public static int Main(string[] args)
    {
        if(args.Length==2 && args[1]=="--refresh-preview")
        {
            try
            {
                string owned=Path.Combine(Path.GetFullPath(args[0]),"Aurora-Mixed-Test.cdr");
                var current=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));
                VG.Document active=current.ActiveDocument;
                if(active==null || !String.Equals(active.FullFileName,owned,StringComparison.OrdinalIgnoreCase) || active.ActivePage.Shapes.Count!=32)
                    throw new Exception("Expected the newly created owned mixed test sheet.");
                Preview(current,active,Path.Combine(Path.GetFullPath(args[0]),"Aurora-Mixed-Test-reference-padded.png"));
                if(active.ActivePage.Shapes.Count!=32)throw new Exception("Temporary preview background was not removed.");
                active.Save();Console.WriteLine("Padded reference exported; editable artwork remains32 shapes; no print.");return 0;
            }
            catch(Exception error){Console.Error.WriteLine(error);return 1;}
        }
        if(args.Length!=1)return 2;
        string folder=Path.GetFullPath(args[0]),output=Path.Combine(folder,"Aurora-Mixed-Test.cdr");
        if(File.Exists(output))return 2;
        var json=new JavaScriptSerializer();
        var spec=(Dictionary<string,object>)json.DeserializeObject(File.ReadAllText(Path.Combine(folder,"artwork-spec.json")));
        VG.Document doc=null,previous=null;bool success=false;
        try
        {
            var app=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));
            previous=app.ActiveDocument;string previousName=previous==null?null:previous.FullFileName;
            doc=app.CreateDocument();doc.Unit=VG.cdrUnit.cdrInch;doc.ActivePage.SetSize(30,18);
            double left=doc.ActivePage.LeftX+1,top=doc.ActivePage.TopY-1;
            var all=app.CreateShapeRange();var report=new List<object>();int cuts=0,open=0,closed=0;
            VG.Color black=app.CreateColor();black.RGBAssign(0,0,0);
            foreach(Dictionary<string,object> item in (object[])spec["shapes"])
            {
                string kind=(string)item["kind"],name=(string)item["name"];
                double x=left+D(item,"x"),y=top-D(item,"y");VG.Shape shape;
                if(kind=="bitmap")
                {
                    var import=doc.ActiveLayer.ImportEx(Path.Combine(folder,(string)item["file"]),VG.cdrFilter.cdrBMP,null);import.Finish();
                    shape=doc.Selection().Shapes[1];shape.SetSize(D(item,"width"),D(item,"height"));
                    shape.SetPositionEx(VG.cdrReferencePoint.cdrTopLeft,x,y);
                }
                else if(kind=="text")
                {
                    shape=doc.ActiveLayer.CreateArtisticText(0,0,(string)item["text"],Font:"Arial",Size:(float)D(item,"size"),
                        Bold:B(item,"bold")?VG.cdrTriState.cdrTrue:VG.cdrTriState.cdrFalse);
                    shape.Outline.SetNoOutline();shape.Fill.ApplyUniformFill(black);
                    shape.SetPositionEx(VG.cdrReferencePoint.cdrTopLeft,x,y);
                }
                else
                {
                    if(kind=="rect")shape=doc.ActiveLayer.CreateRectangle2(x,y-D(item,"height"),D(item,"width"),D(item,"height"));
                    else if(kind=="ellipse" || kind=="arc")
                        shape=doc.ActiveLayer.CreateEllipse2(x+D(item,"width")/2,y-D(item,"height")/2,
                            D(item,"width")/2,D(item,"height")/2,kind=="arc"?20:0,kind=="arc"?330:360,false);
                    else if(kind=="line")shape=doc.ActiveLayer.CreateLineSegment(x,y,left+D(item,"x2"),top-D(item,"y2"));
                    else if(kind=="polyline")
                    {
                        var curve=app.CreateCurve(doc);var vertices=(object[])item["vertices"];
                        var first=(object[])vertices[0];var sub=curve.CreateSubPath(left+Convert.ToDouble(first[0]),top-Convert.ToDouble(first[1]));
                        for(int i=1;i<vertices.Length;i++)
                        {var point=(object[])vertices[i];sub.AppendLineSegment(left+Convert.ToDouble(point[0]),top-Convert.ToDouble(point[1]));}
                        shape=doc.ActiveLayer.CreateCurve(curve);
                    }
                    else throw new Exception("Unknown shape: "+kind);
                    if(B(item,"fill")){shape.Outline.SetNoOutline();shape.Fill.ApplyUniformFill(black);}
                    else
                    {
                        shape.Fill.ApplyNoFill();shape.Outline.Width=B(item,"hairline")?.001:D(item,"points")/72;
                        if(item.ContainsKey("color"))
                        {var color=(object[])item["color"];shape.Outline.Color.RGBAssign(Convert.ToInt32(color[0]),Convert.ToInt32(color[1]),Convert.ToInt32(color[2]));}
                        else shape.Outline.Color.RGBAssign(0,0,0);
                    }
                }
                shape.Name=name;
                if(B(item,"hairline"))
                {
                    shape.ConvertToCurves();
                    if(shape.Curve.SubPaths.Count!=1)throw new Exception("Unexpected cut subpaths: "+name);
                    bool isClosed=shape.Curve.SubPaths[1].Closed;
                    if((kind=="arc" || kind=="polyline")==isClosed)throw new Exception("Incorrect open/closed path: "+name);
                    cuts++;if(isClosed)closed++;else open++;
                }
                all.Add(shape);
                report.Add(new {name,kind,x_inches=D(item,"x")+1,y_inches=D(item,"y")+1,
                    width_inches=shape.SizeWidth,height_inches=shape.SizeHeight,
                    hairline_cut=B(item,"hairline"),outline_width_inches=(kind=="text" || kind=="bitmap" || B(item,"fill"))?0:shape.Outline.Width});
            }
            if(cuts!=5 || closed!=3 || open!=2)throw new Exception("Unexpected cutting count.");
            var ps=doc.PrintSettings;ps.Reset();ps.SelectPrinter("Aurora JobServer (Test Capture)");
            ps.PageMatchingMode=VG.PrnPageMatchingMode.prnPageMatchPrinterDefault;
            ps.Layout.Placement=VG.PrnPlaceType.prnPlaceAsInDocument;ps.Layout.PrintTiledPages=false;
            ps.PrintToFile=false;ps.Copies=1;ps.Options.PrintVectors=true;ps.Options.PrintBitmaps=true;ps.Options.PrintText=true;
            ps.Options.RasterizePage=false;ps.Options.UseColorProfile=false;ps.Options.ColorMode=VG.PrnColorMode.prnModeFullColor;
            Preview(app,doc,Path.Combine(folder,"Aurora-Mixed-Test-reference-only.png"));
            var save=app.CreateStructSaveAsOptions();save.Version=VG.cdrFileVersion.cdrVersion17;doc.SaveAs(output,save);
            doc.Activate();app.Visible=true;app.ActiveWindow.ActiveView.ToFitAllObjects();
            File.WriteAllText(output+".json",json.Serialize(new {state="mixed_test_graphic_open_in_X7",document=output,
                previous_document=previousName,page_inches=new[]{doc.ActivePage.SizeWidth,doc.ActivePage.SizeHeight},
                shapes=report,shape_count=doc.ActivePage.Shapes.Count,cut_paths=cuts,closed_paths=closed,open_paths=open,
                bitmap_pixels=new[]{501,250},printer=ps.Printer.Name,placement=ps.Layout.Placement.ToString(),
                required_output_mode="Both Raster and Vector",printer_defaults_changed=false,print_called=false,physical_device_io=false}));
            success=true;Console.WriteLine("Mixed test graphic saved and opened; five cuts, three closed/two open. No print sent.");return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
        finally{if(!success){if(doc!=null)((VG.IVGDocument)doc).Close();if(previous!=null)previous.Activate();}}
    }
}
