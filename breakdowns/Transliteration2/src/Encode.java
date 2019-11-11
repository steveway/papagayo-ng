import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;

class Encode
{

  Encode (){
    System.out.println("fuck");
  }
  public static void main(String[] paramArrayOfString)
  {
    Transliterator localTransliterator = new Transliterator();
    try
    {
      FileInputStream localFileInputStream = new FileInputStream(new File("input_en.txt"));
      BufferedReader localBufferedReader = new BufferedReader(new InputStreamReader(localFileInputStream, "UTF8"));
      
      FileOutputStream localFileOutputStream = new FileOutputStream(new File("output_en.txt"));
      BufferedWriter localBufferedWriter = new BufferedWriter(new OutputStreamWriter(localFileOutputStream, "UTF8"));
      
      localTransliterator.encoder(localBufferedReader, localBufferedWriter);
      //String s = localTransliterator.encoder("කියන්න");

      //System.out.println("string is",s);
      System.out.println("Encoded - Si to En");
      localBufferedWriter.close();
    }
    catch (IOException localIOException)
    {
      System.out.println(localIOException.toString());
    }
  }
}
