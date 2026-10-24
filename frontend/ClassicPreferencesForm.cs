using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

namespace Aurora.Frontend
{
    public sealed class ProcessEditor : GroupBox
    {
        public readonly NumericUpDown Power,Speed,Ppi;
        public event EventHandler ValuesChanged;
        public ProcessEditor(string title,int x,int y,int width,bool ppi,decimal maxSpeed)
        {
            Text=title;Location=new Point(x,y);Size=new Size(width,205);
            int columns=ppi?3:2,cell=(width-12)/columns;
            Power=Column("POWER",0,cell,0,100,2,100,"100%");
            Speed=Column("SPEED",1,cell,.001M,maxSpeed,3,1000,maxSpeed+" ips");
            if(ppi) Ppi=Column("PPI",2,cell,5,1000,0,1,"1000");
        }
        NumericUpDown Column(string label,int index,int cell,decimal min,decimal max,int decimals,int scale,string upper)
        {
            int x=6+index*cell;
            Controls.Add(new Label {Text=label,Location=new Point(x,20),Size=new Size(cell,18),Font=new Font("Segoe UI",8)});
            Controls.Add(new Label {Text=upper,Location=new Point(x,39),Size=new Size(cell,18),Font=new Font("Segoe UI",7.5F)});
            TrackBar slider=new TrackBar {Orientation=Orientation.Vertical,Minimum=(int)(min*scale),Maximum=(int)(max*scale),TickStyle=TickStyle.None,
                Location=new Point(x+10,57),Size=new Size(36,98),SmallChange=1,LargeChange=scale};
            NumericUpDown number=new NumericUpDown {Minimum=min,Maximum=max,DecimalPlaces=decimals,Increment=1M/scale,
                Location=new Point(x,165),Size=new Size(cell-4,25),Font=new Font("Segoe UI",8F),AccessibleName=titleFor(label)};
            slider.Value=slider.Minimum;number.Value=min;
            slider.ValueChanged+=delegate {number.Value=(decimal)slider.Value/scale;};
            number.ValueChanged+=delegate {slider.Value=(int)(number.Value*scale);if(ValuesChanged!=null) ValuesChanged(this,EventArgs.Empty);};
            Controls.Add(slider);Controls.Add(number);return number;
        }
        string titleFor(string field) {return Text+" "+field;}
        public void Set(decimal power,decimal speed,int ppi)
        {Power.Value=power;Speed.Value=speed;if(Ppi!=null) Ppi.Value=ppi;}
    }

    public sealed class OrientationPicture : Control
    {
        readonly int angle;readonly bool mirror;
        public OrientationPicture(int angle,bool mirror,int x,int y)
        {this.angle=angle;this.mirror=mirror;Location=new Point(x,y);Size=new Size(55,55);DoubleBuffered=true;}
        protected override void OnPaint(PaintEventArgs args)
        {
            args.Graphics.Clear(Color.Black);args.Graphics.TranslateTransform(27,27);
            args.Graphics.RotateTransform(angle);if(mirror) args.Graphics.ScaleTransform(-1,1);
            using(Font font=new Font("Times New Roman",35,FontStyle.Bold))
                args.Graphics.DrawString("R",font,Brushes.Red,-25,-28);
        }
    }

    public sealed class ClassicPreferencesForm : Form
    {
        readonly List<Action<ClassicSettings,bool>> bindings=new List<Action<ClassicSettings,bool>>();
        readonly Dictionary<string,Control> named=new Dictionary<string,Control>();
        readonly List<Dimension> dimensions=new List<Dimension>();
        readonly ClassicPresets presets;
        readonly TabControl tabs=new TabControl();
        readonly ComboBox material=new ComboBox(),colorProfile=new ComboBox();
        readonly DataGridView grid=new DataGridView();
        readonly Label rgb=new Label(),status=new Label();
        readonly Label travelUnits=new Label();
        readonly ProcessEditor raster,vector,color;
        readonly Button units=new Button();
        readonly Action<ClassicSettings,Action,Action<string>> nativeSave;
        Button saveButton,cancelButton;
        bool busy;
        ClassicSettings working;
        bool updating,mm;
        int selectedColor=11;
        public ClassicSettings Result {get;private set;}
        public TabControl Tabs {get {return tabs;}}

        sealed class Dimension
        {public string Field;public NumericUpDown Number;public decimal Inches,Min,Max;public bool Dirty;}
        public ClassicPreferencesForm(ClassicSettings initial,string presetDirectory) : this(initial,presetDirectory,null) { }
        public ClassicPreferencesForm(ClassicSettings initial,string presetDirectory,Action<ClassicSettings,Action,Action<string>> nativeSave)
        {
            this.nativeSave=nativeSave;
            working=initial.Clone();presets=new ClassicPresets(presetDirectory);
            Text="Aurora Properties — Complete Controls Preview";Font=new Font("Segoe UI",9F);
            AutoScaleMode=AutoScaleMode.Dpi;ClientSize=new Size(640,690);FormBorderStyle=FormBorderStyle.FixedDialog;
            MaximizeBox=false;MinimizeBox=false;StartPosition=FormStartPosition.CenterScreen;
            tabs.Location=new Point(10,10);tabs.Size=new Size(620,600);tabs.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right|AnchorStyles.Bottom;
            TabPage output=new TabPage("Laser Output Control"),advanced=new TabPage("Advanced"),colors=new TabPage("Color Settings"),about=new TabPage("About");
            tabs.TabPages.AddRange(new TabPage[]{output,advanced,colors,about});Controls.Add(tabs);
            foreach(TabPage page in tabs.TabPages) page.AutoScroll=true;

            GroupBox modes=Group(output,"Output Modes",12,12,190,205);
            Radios(modes,"Output",new object[]{ClassicOutput.RasterOnly,ClassicOutput.VectorOnly,ClassicOutput.RasterAndVector},
                new string[]{"Raster Only","Vector Only","Both Raster and Vector"},10,21,20);
            Check(modes,"UseColors","Use Color Settings",10,86);
            Check(modes,"SortColors","Sort Color Vectors",26,108);
            Check(modes,"PauseColors","Pause Between Colors",26,130);
            Check(modes,"InvertRaster","Invert Raster Output",10,154);
            Check(modes,"BottomUp","Bottom-Up Engraving",10,176);
            raster=new ProcessEditor("Raster Settings",212,12,180,false,150);
            vector=new ProcessEditor("Vector Settings",402,12,180,true,15);output.Controls.Add(raster);output.Controls.Add(vector);

            GroupBox focus=Group(output,"Focus",12,232,190,190);
            Radios(focus,"Focus",new object[]{ClassicFocus.None,ClassicFocus.Manual,ClassicFocus.Thickness,ClassicFocus.Autofocus},
                new string[]{"No Focus at Start","Manual Focus at Start","Material Thickness","Autofocus"},10,21,22);
            DimensionField(focus,"ThicknessInches","Amount:",25,87,70,0,18);
            named["FocusAutofocus"].Location=new Point(10,118);
            Check(focus,"Autostart","Autostart",10,143);Check(focus,"BeamConstantlyOn","Beam Constantly On",10,165);
            GroupBox plate=Group(output,"Plate Size",212,232,180,130);
            DimensionField(plate,"PlateWidthInches","Width",10,26,72,.001M,30);
            DimensionField(plate,"PlateHeightInches","Height",10,59,72,.001M,18);
            Check(plate,"Cylindrical","Cylindrical Mode",10,96);
            GroupBox offset=Group(output,"Plate Offset",402,232,180,190);
            DimensionField(offset,"OffsetXInches","Horizontal",10,26,80,-30,30);
            DimensionField(offset,"OffsetYInches","Vertical",10,59,80,-18,18);
            Check(offset,"CenterHorizontal","Use Horizontal Plate Center",10,112);
            Check(offset,"CenterVertical","Use Vertical Plate Center",10,139);
            units.Text="in / mm";units.Location=new Point(260,382);units.Size=new Size(82,28);units.AccessibleName="Units";
            units.Click+=delegate {ToggleUnits();};output.Controls.Add(units);
            GroupBox materialGroup=Group(output,"Material Setting",12,438,260,100);
            material.Location=new Point(12,23);material.Size=new Size(235,25);material.MaxLength=64;material.AccessibleName="Material Setting";
            materialGroup.Controls.Add(material);
            Button saveMaterial=Button(materialGroup,"Save",12,57,106,delegate {SavePreset(false);});
            Button deleteMaterial=Button(materialGroup,"Delete",135,57,112,delegate {DeletePreset(false);});
            saveMaterial.AccessibleName="Save Material";deleteMaterial.AccessibleName="Delete Material";
            material.SelectionChangeCommitted+=delegate {Guard(delegate {ApplySettings(presets.Load("material",material.Text));});};

            GroupBox laser=Group(advanced,"Laser Settings",12,12,220,96);
            Choice(laser,"Resolution","Resolution",12,24,98,ClassicSettings.Resolutions);
            NumericUpDown travel=Number(laser,"TravelSpeed","Travel Speed",12,59,98,.001M,250,3,76);
            travelUnits.Location=new Point(188,62);travelUnits.Size=new Size(31,20);travelUnits.AccessibleName="Travel speed units";
            laser.Controls.Add(travelUnits);
            travel.ValueChanged+=delegate {
                if(!updating && working!=null && working.Version==1)
                {working.Version=2;travelUnits.Text="ips";status.Text="Travel speed now uses ips. Unverified travel values remain held.";status.ForeColor=Color.Navy;}
            };
            GroupBox bitmap=Group(advanced,"Bitmap Contrast Settings",12,121,220,310);
            Radios(bitmap,"BitmapMode",new object[]{ClassicBitmap.ClipArt,ClassicBitmap.Photo,ClassicBitmap.Custom},new string[]{"Clip Art","Photo","Custom"},12,23,22);
            Check(bitmap,"DitherBitmaps","Dither Bitmaps",17,95);
            Panel algorithms=new Panel {Location=new Point(16,120),Size=new Size(199,109)};bitmap.Controls.Add(algorithms);
            Radios(algorithms,"Dither",new object[]{ClassicDither.Ordered4,ClassicDither.Ordered8,ClassicDither.FloydSteinberg,ClassicDither.Jarvis,ClassicDither.Stucki},
                new string[]{"Ordered — 4 × 4","Ordered — 8 × 8","Floyd-Steinberg (Fine)","Jarvis (Medium)","Stucki (Coarse)"},14,0,21);
            Check(bitmap,"ManualContrast","Manual Contrast Control",12,235);
            Number(bitmap,"ContrastLow","Low",10,275,0,0,255,0,61);
            Number(bitmap,"ContrastHigh","High",79,275,0,0,255,0,61);
            Number(bitmap,"ContrastColors","# Colors",148,275,0,2,256,0,61);
            GroupBox orientation=Group(advanced,"Plate Orientation",247,12,335,157);
            object[] orient={ClassicOrientation.Normal,ClassicOrientation.Left90,ClassicOrientation.Right90,ClassicOrientation.UpsideDown};
            string[] labels={"0°\r\nNormal","90°\r\nLeft","90°\r\nRight","180°\r\nUpside Down"};
            for(int i=0;i<4;i++)
            {orientation.Controls.Add(new OrientationPicture(i==1?-90:i==2?90:i==3?180:0,false,14+i*80,27));Radio(orientation,"Orientation",orient[i],labels[i],12+i*80,93,78,49);}
            GroupBox engraving=Group(advanced,"Engraving Orientation",247,184,335,128);
            engraving.Controls.Add(new OrientationPicture(0,false,45,24));engraving.Controls.Add(new OrientationPicture(0,true,215,24));
            Radio(engraving,"Mirror",false,"Normal",32,87,100,25);Radio(engraving,"Mirror",true,"Reverse / Mirror",193,87,135,25);
            GroupBox stamp=Group(advanced,"Rubber Stamp Options",247,326,335,105);
            Check(stamp,"RubberStamp","Enable",12,24);
            Button stampDetails=Button(stamp,"Factory Default 1",108,55,211,delegate {
                MessageBox.Show(this,"The original stamp profile's parameter dialog has not been supplied yet. The named profile is retained; stamp output remains held until its settings can be compared with XP.","Factory Default 1",MessageBoxButtons.OK,MessageBoxIcon.Information);
            });named.Add("StampDetails",stampDetails);
            GroupBox location=Group(advanced,"JBS Output File Location",12,444,570,88);
            TextBox path=new TextBox {Location=new Point(10,22),Size=new Size(445,25),MaxLength=512,AccessibleName="JBS Output File Location"};
            location.Controls.Add(path);bindings.Add((s,read)=> {if(read) s.OutputDirectory=path.Text;else path.Text=s.OutputDirectory;});
            Button(location,"Browse…",465,21,91,delegate {
                using(FolderBrowserDialog folder=new FolderBrowserDialog {Description="Choose an output-folder preference for this preview. No jobs are written here.",ShowNewFolderButton=false})
                {if(Directory.Exists(path.Text)) folder.SelectedPath=path.Text;if(folder.ShowDialog(this)==DialogResult.OK) path.Text=folder.SelectedPath;}
            });
            Check(location,"DefaultFilename","Use Default Filename: Default.jbs",10,51);
            Check(location,"AppendDateTime","Append Date/Time",319,51);
            Label model=new Label {Text="Laser Model:",Location=new Point(12,547),Size=new Size(95,22)};advanced.Controls.Add(model);
            ComboBox models=new ComboBox {DropDownStyle=ComboBoxStyle.DropDownList,Location=new Point(108,543),Size=new Size(474,25),AccessibleName="Laser Model"};models.Items.Add("Aurora");models.SelectedIndex=0;advanced.Controls.Add(models);

            grid.Location=new Point(12,17);grid.Size=new Size(290,383);grid.AllowUserToAddRows=false;grid.AllowUserToDeleteRows=false;
            grid.AllowUserToResizeRows=false;grid.RowHeadersVisible=false;grid.MultiSelect=false;grid.SelectionMode=DataGridViewSelectionMode.FullRowSelect;
            grid.BackgroundColor=SystemColors.Window;grid.AccessibleName="Color process table";grid.AutoGenerateColumns=false;
            grid.Columns.Add(new DataGridViewCheckBoxColumn {Name="Enabled",HeaderText="",Width=25});
            grid.Columns.Add(new DataGridViewTextBoxColumn {Name="Swatch",HeaderText="",Width=18,ReadOnly=true});
            foreach(string column in new string[]{"Color","Power","Speed","PPI"}) grid.Columns.Add(new DataGridViewTextBoxColumn {
                Name=column,HeaderText=column,ReadOnly=true,Width=column=="Color"?72:column=="Speed"?64:45});
            colors.Controls.Add(grid);
            color=new ProcessEditor("Selected Color",314,17,268,true,150);colors.Controls.Add(color);
            color.ValuesChanged+=delegate {if(!updating) {SaveColor();RefreshRow(selectedColor);}};
            grid.SelectionChanged+=delegate {
                if(updating || grid.SelectedRows.Count==0) return;
                SaveColor();selectedColor=grid.SelectedRows[0].Index;LoadColor();
            };
            grid.CurrentCellDirtyStateChanged+=delegate {if(grid.IsCurrentCellDirty) grid.CommitEdit(DataGridViewDataErrorContexts.Commit);};
            grid.CellValueChanged+=delegate(object sender,DataGridViewCellEventArgs args) {
                if(!updating && args.RowIndex>=0 && args.ColumnIndex==0) working.Colors[args.RowIndex].Enabled=Convert.ToBoolean(grid.Rows[args.RowIndex].Cells[0].Value);
            };
            GroupBox colorGroup=Group(colors,"Current Color Profile",314,249,268,112);
            colorProfile.Location=new Point(12,23);colorProfile.Size=new Size(243,25);colorProfile.MaxLength=64;colorProfile.AccessibleName="Current Color Profile";colorGroup.Controls.Add(colorProfile);
            Button(colorGroup,"Save",12,67,110,delegate {SavePreset(true);});Button(colorGroup,"Delete",139,67,116,delegate {DeletePreset(true);});
            colorProfile.SelectionChangeCommitted+=delegate {Guard(delegate {
                ClassicSettings loaded=colorProfile.Text=="All_colors (screenshot reference)"?new ClassicSettings():presets.Load("color",colorProfile.Text);
                working.Colors=loaded.Clone().Colors;working.ColorProfile=colorProfile.Text;RefreshColors();
            });};
            rgb.Location=new Point(12,414);rgb.Size=new Size(570,28);colors.Controls.Add(rgb);
            colors.Controls.Add(new Label {Text="Edit the selected color using POWER, SPEED and PPI. Check marks enable colors.",Location=new Point(12,456),Size=new Size(560,45)});
            about.Controls.Add(new Label {Text="Aurora JobServer — original Preferences controls\r\n\r\n"+(nativeSave==null?"This is a complete-controls preview. Save preview and presets retain the selected values locally. This window does not change the installed printer and cannot run the laser.":"OK saves a complete settings snapshot in the print request. Cancel discards changes to that request. Material and color presets are stored for this Windows user. Jobs using unverified options are held in JobServer.")+"\r\n\r\nThe 16-color reference table comes from your screenshot. New engraving behavior still requires comparison with the XP driver's job output.",Location=new Point(20,25),Size=new Size(545,270)});

            status.Text="Preview only — no printer settings or laser jobs are changed.";status.ForeColor=Color.Navy;
            status.Location=new Point(12,618);status.Size=new Size(616,33);status.Anchor=AnchorStyles.Left|AnchorStyles.Right|AnchorStyles.Bottom;Controls.Add(status);
            Button save=Button(this,"Save preview",394,654,112,delegate {Guard(delegate {Result=ReadSettings();Close();});});
            Button cancel=Button(this,"Cancel",518,654,110,delegate {Result=null;Close();});save.Anchor=cancel.Anchor=AnchorStyles.Bottom|AnchorStyles.Right;AcceptButton=save;CancelButton=cancel;
            // Replace the preview-only handler when hosted by the native request.
            if(nativeSave!=null)
            {
                Controls.Remove(save);save.Dispose();save=Button(this,"OK",394,654,112,SaveChanges);save.Anchor=AnchorStyles.Bottom|AnchorStyles.Right;AcceptButton=save;
                Text="Aurora Laser — Printer Properties";ShowInTaskbar=false;
                status.Text="Additional options are saved with each print. Unverified options hold the job for review.";
            }
            saveButton=save;cancelButton=cancel;
            FormClosing+=delegate(object sender,FormClosingEventArgs args) {if(busy) args.Cancel=true;};
            Shown+=delegate {Rectangle area=Screen.FromControl(this).WorkingArea;if(Height>area.Height) Height=area.Height;};
            RefreshPresets();ApplySettings(initial);
        }

        static GroupBox Group(Control parent,string text,int x,int y,int w,int h)
        {GroupBox group=new GroupBox {Text=text,Location=new Point(x,y),Size=new Size(w,h)};parent.Controls.Add(group);return group;}
        Button Button(Control parent,string text,int x,int y,int w,Action action)
        {Button button=new Button {Text=text,Location=new Point(x,y),Size=new Size(w,27)};button.Click+=delegate {Guard(action);};parent.Controls.Add(button);return button;}
        void Guard(Action action) {try {action();} catch(Exception error) {status.Text=error.Message;status.ForeColor=Color.DarkRed;}}
        static FieldInfo Field(string field) {return typeof(ClassicSettings).GetField(field);}
        CheckBox Check(Control parent,string field,string label,int x,int y)
        {
            CheckBox box=new CheckBox {Text=label,Location=new Point(x,y),AutoSize=true,AccessibleName=field};parent.Controls.Add(box);named.Add(field,box);
            bindings.Add((s,read)=> {if(read) Field(field).SetValue(s,box.Checked);else box.Checked=(bool)Field(field).GetValue(s);});
            box.CheckedChanged+=delegate {Dependencies();};return box;
        }
        NumericUpDown Number(Control parent,string field,string label,int x,int y,int offset,decimal min,decimal max,int digits,int width=84)
        {
            parent.Controls.Add(new Label {Text=label,Location=new Point(x,offset==0?y-19:y+3),Size=new Size(offset==0?width:offset,20)});
            NumericUpDown number=new NumericUpDown {Location=new Point(x+offset,y),Size=new Size(width,25),Minimum=min,Maximum=max,DecimalPlaces=digits,Increment=digits==3?.001M:1,AccessibleName=field};
            parent.Controls.Add(number);named.Add(field,number);
            bindings.Add((s,read)=> {FieldInfo f=Field(field);if(read) f.SetValue(s,f.FieldType==typeof(int)?(object)(int)number.Value:number.Value);else number.Value=Convert.ToDecimal(f.GetValue(s),CultureInfo.InvariantCulture);});return number;
        }
        void Choice(Control parent,string field,string label,int x,int y,int offset,int[] values)
        {
            parent.Controls.Add(new Label {Text=label,Location=new Point(x,y+4),Size=new Size(offset,20)});
            ComboBox combo=new ComboBox {DropDownStyle=ComboBoxStyle.DropDownList,Location=new Point(x+offset,y),Size=new Size(94,25),AccessibleName=field};
            foreach(int value in values) combo.Items.Add(value);parent.Controls.Add(combo);named.Add(field,combo);
            bindings.Add((s,read)=> {if(read) Field(field).SetValue(s,(int)combo.SelectedItem);else combo.SelectedItem=Field(field).GetValue(s);});
        }
        void Radios(Control parent,string field,object[] values,string[] labels,int x,int y,int step)
        {for(int i=0;i<values.Length;i++) Radio(parent,field,values[i],labels[i],x,y+i*step,180,22);}
        void Radio(Control parent,string field,object value,string label,int x,int y,int width,int height)
        {
            RadioButton radio=new RadioButton {Text=label,Location=new Point(x,y),Size=new Size(width,height),AccessibleName=field+value};
            parent.Controls.Add(radio);named.Add(field+value,radio);
            bindings.Add((s,read)=> {if(read) {if(radio.Checked) Field(field).SetValue(s,value);} else radio.Checked=Object.Equals(Field(field).GetValue(s),value);});
            radio.CheckedChanged+=delegate {Dependencies();};
        }
        void DimensionField(Control parent,string field,string label,int x,int y,int offset,decimal min,decimal max)
        {
            parent.Controls.Add(new Label {Text=label,Location=new Point(x,y+3),Size=new Size(offset,22)});
            NumericUpDown number=new NumericUpDown {Location=new Point(x+offset,y),Size=new Size(76,25),DecimalPlaces=3,Minimum=min,Maximum=max,Increment=.001M,AccessibleName=field};
            Dimension binding=new Dimension {Field=field,Number=number,Min=min,Max=max};dimensions.Add(binding);parent.Controls.Add(number);named.Add(field,number);
            number.ValueChanged+=delegate {if(!updating) binding.Dirty=true;};
        }
        void CaptureDimensions(ClassicSettings state)
        {
            foreach(Dimension d in dimensions)
            {if(d.Dirty) {d.Inches=mm?Decimal.Round(d.Number.Value/25.4M,6):d.Number.Value;d.Dirty=false;}Field(d.Field).SetValue(state,d.Inches);}
        }
        public void ToggleUnits()
        {
            CaptureDimensions(working);mm=!mm;updating=true;
            foreach(Dimension d in dimensions)
            {
                decimal low=Decimal.Floor(d.Min*(mm?25.4M:1)*1000)/1000,high=Decimal.Ceiling(d.Max*(mm?25.4M:1)*1000)/1000;
                d.Number.Minimum=Math.Min(d.Number.Minimum,low);d.Number.Maximum=Math.Max(d.Number.Maximum,high);
                d.Number.Value=Decimal.Round(d.Inches*(mm?25.4M:1),3);
                d.Number.Minimum=low;d.Number.Maximum=high;
            }
            units.Text=mm?"mm → in":"in → mm";updating=false;
        }
        public void ApplySettings(ClassicSettings settings)
        {
            settings.Validate();working=settings.Clone();updating=true;
            foreach(var binding in bindings) binding(working,false);
            travelUnits.Text=working.Version==1?"v1":"ips";
            if(working.Version==1)
            {status.Text="Legacy travel value retained; job stays held. Change Travel Speed to select a value in ips.";status.ForeColor=Color.DarkRed;}
            else if(status.Text.StartsWith("Legacy travel value",StringComparison.Ordinal))
            {status.Text="Travel speed uses ips. Unverified travel values remain held.";status.ForeColor=Color.Navy;}
            raster.Set(working.RasterPower,working.RasterSpeed,1000);vector.Set(working.VectorPower,working.VectorSpeed,working.VectorPpi);
            foreach(Dimension d in dimensions)
            {d.Inches=(decimal)Field(d.Field).GetValue(working);d.Number.Value=Decimal.Round(d.Inches*(mm?25.4M:1),3);d.Dirty=false;}
            colorProfile.Text=working.ColorProfile;updating=false;RefreshColors();Dependencies();
        }
        public ClassicSettings ReadSettings()
        {
            SaveColor();ClassicSettings result=working.Clone();foreach(var binding in bindings) binding(result,true);
            result.RasterPower=raster.Power.Value;result.RasterSpeed=raster.Speed.Value;result.VectorPower=vector.Power.Value;result.VectorSpeed=vector.Speed.Value;result.VectorPpi=(int)vector.Ppi.Value;
            result.ColorProfile=colorProfile.Text;CaptureDimensions(result);result.Validate();return result;
        }
        public void SaveChanges()
        {
            if(busy) return;
            Guard(delegate {
                ClassicSettings selected=ReadSettings();
                if(nativeSave==null) {Result=selected;Close();return;}
                busy=true;tabs.Enabled=false;saveButton.Enabled=false;cancelButton.Enabled=false;status.Text="Saving printer preferences…";
                try {nativeSave(selected,delegate {busy=false;Result=selected;Close();},delegate(string error) {SaveFailed(error);});}
                catch(Exception error) {SaveFailed(error.Message);}
            });
        }
        void SaveFailed(string message)
        {busy=false;tabs.Enabled=true;saveButton.Enabled=true;cancelButton.Enabled=true;status.Text=message;status.ForeColor=Color.DarkRed;}
        void SaveColor()
        {
            if(updating || working==null || color==null) return;
            working.Colors[selectedColor].PowerPercent=color.Power.Value;working.Colors[selectedColor].SpeedIps=color.Speed.Value;working.Colors[selectedColor].Ppi=(int)color.Ppi.Value;
        }
        void LoadColor()
        {
            updating=true;ClassicColor c=working.Colors[selectedColor];color.Set(c.PowerPercent,c.SpeedIps,c.Ppi);
            rgb.Text="Selected Color R/G/B #   "+c.R+"/"+c.G+"/"+c.B;updating=false;
        }
        void RefreshRow(int index)
        {
            if(grid.Rows.Count!=16) return;bool previous=updating;updating=true;
            ClassicColor c=working.Colors[index];DataGridViewRow row=grid.Rows[index];
            row.Cells[0].Value=c.Enabled;row.Cells[1].Value="";row.Cells[1].Style.BackColor=Color.FromArgb(c.R,c.G,c.B);row.Cells[1].Style.SelectionBackColor=Color.FromArgb(c.R,c.G,c.B);
            row.Cells[2].Value=c.Name;row.Cells[3].Value=c.PowerPercent.ToString("0.##");row.Cells[4].Value=c.SpeedIps.ToString("0.000");row.Cells[5].Value=c.Ppi;
            updating=previous;
        }
        void RefreshColors()
        {
            updating=true;grid.Rows.Clear();for(int i=0;i<16;i++) grid.Rows.Add();for(int i=0;i<16;i++) RefreshRow(i);
            grid.CurrentCell=grid.Rows[selectedColor].Cells[2];grid.ClearSelection();grid.Rows[selectedColor].Selected=true;updating=false;LoadColor();
        }
        void RefreshPresets()
        {
            string m=material.Text,c=colorProfile.Text;material.Items.Clear();material.Items.AddRange(presets.Names("material"));material.Text=m;
            colorProfile.Items.Clear();colorProfile.Items.Add("All_colors (screenshot reference)");colorProfile.Items.AddRange(presets.Names("color"));colorProfile.Text=c;
        }
        void SavePreset(bool colorsOnly)
        {
            string kind=colorsOnly?"color":"material",name=colorsOnly?colorProfile.Text:material.Text;
            if(colorsOnly && name=="All_colors (screenshot reference)") throw new InvalidOperationException("Enter a new color-profile name to save your edited table.");
            if(presets.Contains(kind,name) && MessageBox.Show(this,"Replace preset '"+name+"'?","Save preset",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes) return;
            SaveColor();ClassicSettings state=colorsOnly?working.Clone():ReadSettings();
            if(colorsOnly) state.ColorProfile=name;
            presets.Save(kind,name,state);RefreshPresets();status.Text="Preset saved locally. No print was submitted.";
        }
        void DeletePreset(bool colorsOnly)
        {
            string kind=colorsOnly?"color":"material",name=colorsOnly?colorProfile.Text:material.Text;
            if(colorsOnly && name=="All_colors (screenshot reference)") throw new InvalidOperationException("The screenshot reference table is built in. Saved color profiles can be deleted.");
            if(MessageBox.Show(this,"Delete preset '"+name+"'?","Delete preset",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes) return;
            presets.Delete(kind,name);if(colorsOnly) colorProfile.Text="";else material.Text="";RefreshPresets();
        }
        void Dependencies()
        {
            if(updating || !named.ContainsKey("StampDetails")) return;
            bool useColors=((CheckBox)named["UseColors"]).Checked;
            named["SortColors"].Enabled=useColors;named["PauseColors"].Enabled=useColors;
            named["ThicknessInches"].Enabled=((RadioButton)named["Focus"+ClassicFocus.Thickness]).Checked;
            bool custom=((RadioButton)named["BitmapMode"+ClassicBitmap.Custom]).Checked;
            named["DitherBitmaps"].Enabled=custom;named["ManualContrast"].Enabled=custom;
            foreach(ClassicDither d in Enum.GetValues(typeof(ClassicDither))) named["Dither"+d].Enabled=custom && ((CheckBox)named["DitherBitmaps"]).Checked;
            bool contrast=custom && ((CheckBox)named["ManualContrast"]).Checked;
            named["ContrastLow"].Enabled=contrast;named["ContrastHigh"].Enabled=contrast;named["ContrastColors"].Enabled=contrast;
            named["StampDetails"].Enabled=((CheckBox)named["RubberStamp"]).Checked;
        }
        public Control Named(string name) {return named[name];}
        public DataGridView ColorGrid {get {return grid;}}
        public ProcessEditor Raster {get {return raster;}}public ProcessEditor Vector {get {return vector;}}public ProcessEditor SelectedColorEditor {get {return color;}}
    }
}
