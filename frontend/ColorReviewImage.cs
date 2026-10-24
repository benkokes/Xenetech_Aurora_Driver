// Experimental RGB snapshots. Not a printer-ready exposure format.
using System;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Windows;
using System.Windows.Media.Imaging;

namespace Aurora.Frontend
{
    public sealed class ColorReviewReport
    {
        public string encoding = "rgb-u8-on-opaque-white-review-only";
        public string coverage_encoding = "nonwhite-u8-review-only";
        public string coverage_limitation = "White artwork cannot be distinguished from the opaque white page background.";
        public string file, sha256, coverage_file, coverage_sha256;
        public int width, height, x_pixels, y_pixels;
        public long nonwhite_pixels;
    }

    internal static class ColorReviewImage
    {
        static string Hash(byte[] bytes)
        {
            using (SHA256 hash = SHA256.Create())
                return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }

        internal static ColorReviewReport Write(BitmapSource bitmap, string directory, int number)
        {
            int width = bitmap.PixelWidth, height = bitmap.PixelHeight;
            if (width <= 0 || height <= 0 || (long)width * height > 15000000)
                throw new ArgumentException("Color review is limited to the measured 167-DPI surface.");
            byte[] row = new byte[width * 4];
            int left = width, top = height, right = -1, bottom = -1;
            long nonwhite = 0;
            for (int y = 0; y < height; y++)
            {
                bitmap.CopyPixels(new Int32Rect(0,y,width,1),row,row.Length,0);
                for (int x = 0; x < width; x++)
                {
                    int p = x * 4;
                    if (row[p+3] != 255) throw new InvalidOperationException("Color review requires the opaque preview composite.");
                    if (row[p] == 255 && row[p+1] == 255 && row[p+2] == 255) continue;
                    nonwhite++;
                    left = Math.Min(left,x); right = Math.Max(right,x);
                    top = Math.Min(top,y); bottom = Math.Max(bottom,y);
                }
            }
            if (right < left) return null;
            ColorReviewReport report = new ColorReviewReport { width = right-left+1, height = bottom-top+1,
                x_pixels = left, y_pixels = top, nonwhite_pixels = nonwhite,
                file = String.Format(CultureInfo.InvariantCulture,"page-{0:000}-color-review.rgb",number),
                coverage_file = String.Format(CultureInfo.InvariantCulture,"page-{0:000}-color-review.coverage",number) };
            byte[] rgb = new byte[report.width*report.height*3], coverage = new byte[report.width*report.height];
            for (int y = top; y <= bottom; y++)
            {
                bitmap.CopyPixels(new Int32Rect(0,y,width,1),row,row.Length,0);
                for (int x = left; x <= right; x++)
                {
                    int p = x*4, target = (y-top)*report.width+x-left;
                    rgb[target*3] = row[p+2]; rgb[target*3+1] = row[p+1]; rgb[target*3+2] = row[p];
                    coverage[target] = (byte)((row[p] == 255 && row[p+1] == 255 && row[p+2] == 255) ? 0 : 255);
                }
            }
            report.sha256 = Hash(rgb); report.coverage_sha256 = Hash(coverage);
            using (FileStream file = new FileStream(Path.Combine(directory,report.file),FileMode.CreateNew)) file.Write(rgb,0,rgb.Length);
            using (FileStream file = new FileStream(Path.Combine(directory,report.coverage_file),FileMode.CreateNew)) file.Write(coverage,0,coverage.Length);
            return report;
        }
    }
}
