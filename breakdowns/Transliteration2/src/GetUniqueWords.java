import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.ArrayList;
import java.util.List;


public class GetUniqueWords {

	/**
	 * @param args
	 * @throws IOException 
	 */
	
	public List<String> getUniqueWords(String str1) throws IOException{
		String[] words;
		List<String> uniqueWords = new ArrayList<String>();
		
		FileInputStream localFileInputStream = new FileInputStream(new File(str1));
		BufferedReader localBufferedReader = new BufferedReader(new InputStreamReader(localFileInputStream, "UTF8"));
		
		String line = localBufferedReader.readLine();
		while(line != null){
			words = line.split("[-!~\\s]+");
			for (int i = 0; i < words.length; i++)
			{
			    if (!(uniqueWords.contains (words[i])))
			    {
			        uniqueWords.add(words[i]);
			    }
			}
			line = localBufferedReader.readLine();
		}
		
		localBufferedReader.close();
		return uniqueWords;
	}
	
	
	public static void main(String[] args) throws IOException {
		// TODO Auto-generated method stub
				
		GetUniqueWords guw = new GetUniqueWords();
		List<String> uniqueWords = new ArrayList<String>();
		
		String fileName = args[0];
		String names[] = fileName.split("\\.");
		String name = names[0];
		String out_name = name.concat("_UniqueWords.txt");
		
		FileOutputStream localFileOutputStream = new FileOutputStream(new File(out_name));
	    BufferedWriter localBufferedWriter = new BufferedWriter(new OutputStreamWriter(localFileOutputStream, "UTF8"));
	    
	    uniqueWords = guw.getUniqueWords(fileName);

	   
		for(String str : uniqueWords){
			localBufferedWriter.write(str);
			localBufferedWriter.write("\n");
		}
		
		localBufferedWriter.close();

	}

}
