// Seeded offscreen composition checks. No spooler, Corel, or device access.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace Aurora.Frontend
{
    public static class SemanticColorCampaign
    {
        static readonly Color[] ColorsToUse={Colors.Black,Colors.Red,Colors.Blue,Colors.Lime,Colors.Magenta,Colors.Navy,
            Colors.Gray,Color.FromRgb(255,128,0),Color.FromRgb(20,80,160),Colors.White};
        static byte[] Pixels(BitmapSource bitmap)
        {byte[] bytes=new byte[bitmap.PixelWidth*bitmap.PixelHeight*4];bitmap.CopyPixels(bytes,bitmap.PixelWidth*4,0);return bytes;}

        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                if(args.Length<1 || args.Length>3)throw new ArgumentException("Expected a new output directory, optional seed and case count.");
                string root=Path.GetFullPath(args[0]);
                if(Directory.Exists(root))throw new ArgumentException("Preserve prior campaign output; choose a new directory.");
                int seed=args.Length>1?Int32.Parse(args[1],CultureInfo.InvariantCulture):1729;
                int count=args.Length>2?Int32.Parse(args[2],CultureInfo.InvariantCulture):64;
                if(count<1 || count>128)throw new ArgumentException("Use 1-128 bounded cases.");
                Directory.CreateDirectory(root);Random random=new Random(seed);
                const int width=96,height=64;const double dpi=167;
                Size size=new Size(width*96.0/dpi,height*96.0/dpi);
                List<object> results=new List<object>();int held=0,worst=0;
                for(int number=0;number<count;number++)
                {
                    string directory=Path.Combine(root,"case-"+number.ToString("000",CultureInfo.InvariantCulture));Directory.CreateDirectory(directory);
                    DrawingGroup drawing=new DrawingGroup();
                    drawing.Children.Add(new GeometryDrawing(Brushes.White,null,new RectangleGeometry(new Rect(size))));
                    for(int shape=0;shape<14;shape++)
                    {
                        double x=random.NextDouble()*(size.Width-8),y=random.NextDouble()*(size.Height-6);
                        double w=3+random.NextDouble()*18,h=3+random.NextDouble()*12;
                        Geometry geometry=shape%3==0?(Geometry)new EllipseGeometry(new Rect(x,y,w,h)):new RectangleGeometry(new Rect(x,y,w,h));
                        SolidColorBrush fill=new SolidColorBrush(ColorsToUse[random.Next(ColorsToUse.Length)]);
                        Pen pen=shape%4==0?new Pen(new SolidColorBrush(ColorsToUse[random.Next(ColorsToUse.Length)]),0.3+random.NextDouble()):null;
                        DrawingGroup group=new DrawingGroup {ClipGeometry=new RectangleGeometry(new Rect(0,0,size.Width,size.Height))};
                        group.Transform=new RotateTransform(random.Next(-12,13),x+w/2,y+h/2);
                        group.Children.Add(new GeometryDrawing(fill,pen,geometry));drawing.Children.Add(group);
                    }
                    if(number%8==0)
                    {
                        DrawingVisual text=new DrawingVisual();
                        using(DrawingContext dc=text.RenderOpen())dc.DrawText(new FormattedText("Aurora",CultureInfo.InvariantCulture,
                            FlowDirection.LeftToRight,new Typeface("Segoe UI"),9,Brushes.Red,dpi/96.0),new Point(4,3));
                        drawing.Children.Add(Intake.Capture(text));
                    }
                    byte[] original=Pixels(Intake.Render(drawing,size,dpi,true,width,height));
                    SemanticColorReport report=SemanticColorLayers.Write(drawing,size,dpi,true,width,height,directory,1);
                    if(report.status!="prepared_offline_flat_color_layers")throw new Exception("Opaque fixture unexpectedly unsupported: "+report.unsupported_reason);
                    int[] loss=new int[width*height*3];
                    foreach(SemanticColorLayer layer in report.layers)
                    {
                        int rgb=Int32.Parse(layer.color.Substring(3),NumberStyles.HexNumber,CultureInfo.InvariantCulture);
                        int[] channels={(rgb>>16)&255,(rgb>>8)&255,rgb&255};ExposureReport image=layer.coverage;
                        byte[] coverage=File.ReadAllBytes(Path.Combine(directory,image.file));
                        for(int p=0;p<coverage.Length;p++)if(coverage[p]>0)
                        {
                            int x=image.x_pixels+p%image.width,y=image.y_pixels+p/image.width;
                            if(x<0 || y<0 || x>=width || y>=height)throw new Exception("Layer left the measured surface.");
                            int target=(y*width+x)*3;
                            for(int c=0;c<3;c++)loss[target+c]+=(255-channels[c])*coverage[p];
                        }
                    }
                    int maximum=0,different=0;long absolute=0;
                    for(int pixel=0;pixel<width*height;pixel++)for(int c=0;c<3;c++)
                    {
                        int predicted=Math.Max(0,Math.Min(255,255-(loss[pixel*3+c]+127)/255));
                        int error=Math.Abs(predicted-original[pixel*4+2-c]);
                        maximum=Math.Max(maximum,error);absolute+=error;if(error>0)different++;
                    }
                    if(BitConverter.ToString(original)!=BitConverter.ToString(Pixels(Intake.Render(drawing,size,dpi,true,width,height))))
                        throw new Exception("Semantic rendering mutated an original drawing.");
                    if(maximum>2)held++;worst=Math.Max(worst,maximum);
                    results.Add(new {index=number,semantic_layers=report.layers.Count,max_channel_error=maximum,
                        differing_channels=different,mean_channel_error=(double)absolute/(width*height*3),
                        review_status=maximum<=2?"within_strict_review_tolerance":"held_exceeds_review_tolerance"});
                    if(maximum>2)File.WriteAllBytes(Path.Combine(directory,"original.bgra"),original);
                }
                object result=new {state="seeded_semantic_composition_campaign_completed",seed=seed,cases=count,
                    worst_channel_error=worst,held_cases=held,source_mutations=0,physical_device_io=false,
                    synthetic_native_checks_not_xp_captures=true,results=results};
                File.WriteAllText(Path.Combine(root,"verification.json"),new JavaScriptSerializer().Serialize(result));
                Console.WriteLine("Completed {0} synthetic native cases; max error {1}; held above tolerance: {2}; no source mutations.",count,worst,held);
                return 0;
            }
            catch(Exception error){Console.Error.WriteLine(error);return 1;}
        }
    }
}
